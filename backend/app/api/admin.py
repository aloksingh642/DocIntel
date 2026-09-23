"""Admin endpoints: processing logs, audit trail, configuration view."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.config import settings
from app.database.session import get_db
from app.extractors.ocr import tesseract_available
from app.models.document import AuditLog, ProcessingLog
from app.models.ops import Webhook, WebhookDelivery
from app.models.user import User
from app.schemas.api import SettingsUpdate, WebhookIn
from app.schemas.common import APIResponse
from app.services.settings_service import SettingsService, TUNABLES

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/processing-logs", summary="Processing stage logs (filterable)")
def processing_logs(
    document_id: int | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    q = db.query(ProcessingLog).order_by(ProcessingLog.id.desc())
    if document_id:
        q = q.filter(ProcessingLog.document_id == document_id)
    if status:
        q = q.filter(ProcessingLog.status == status)
    logs = q.limit(limit).all()
    return APIResponse(data=[
        {"id": l.id, "document_id": l.document_id, "stage": l.stage,
         "status": l.status, "message": l.message,
         "processing_time": l.processing_time,
         "created_at": l.created_at.isoformat() if l.created_at else None}
        for l in logs
    ])


@router.get("/audit-logs", summary="Audit trail")
def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit_view")),
) -> APIResponse:
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return APIResponse(data=[
        {"id": a.id, "user_id": a.user_id, "action": a.action, "entity": a.entity,
         "entity_id": a.entity_id, "old_value": a.old_value, "new_value": a.new_value,
         "created_at": a.created_at.isoformat() if a.created_at else None}
        for a in rows
    ])


@router.get("/config", summary="Runtime configuration (non-secret)")
def runtime_config(db: Session = Depends(get_db),
                   _: User = Depends(require_permission("read"))) -> APIResponse:
    svc = SettingsService(db)
    return APIResponse(data={
        "classification_confidence_threshold": svc.get("classification_confidence_threshold"),
        "duplicate_similarity_threshold": svc.get("duplicate_similarity_threshold"),
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "allowed_extensions": sorted(settings.ALLOWED_EXTENSIONS),
        "ai_provider": settings.AI_PROVIDER,
        "ocr_available": tesseract_available(),
        "database": "postgresql" if "postgres" in settings.DATABASE_URL else "sqlite",
    })


# --------------------------- Runtime settings ------------------------------- #


@router.get("/settings", summary="List tunable settings (admin-editable)")
def list_settings(db: Session = Depends(get_db),
                  _: User = Depends(require_permission("read"))) -> APIResponse:
    return APIResponse(data=SettingsService(db).all_current())


@router.put("/settings", summary="Update runtime settings (admin)",
            description="Overrides take effect immediately across classification, "
            "duplicate detection and skill matching — no redeploy.")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage_thresholds")),
) -> APIResponse:
    svc = SettingsService(db)
    updated: dict[str, float] = {}
    for key, raw in payload.values.items():
        if key not in TUNABLES:
            raise HTTPException(400, detail={"code": "UNKNOWN_SETTING",
                                             "message": f"'{key}' is not tunable."})
        try:
            updated[key] = svc.set(key, raw, user.id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, detail={"code": "BAD_VALUE", "message": str(exc)}) from exc
    db.add(AuditLog(user_id=user.id, action="update_settings", entity="settings",
                    new_value=", ".join(f"{k}={v}" for k, v in updated.items())))
    db.commit()
    return APIResponse(data=updated, message="Settings updated.")


# ------------------------------ Webhooks ------------------------------------ #


@router.get("/webhooks", summary="List webhooks with recent delivery health")
def list_webhooks(db: Session = Depends(get_db),
                  _: User = Depends(require_permission("read"))) -> APIResponse:
    hooks = db.query(Webhook).order_by(Webhook.id).all()
    data = []
    for h in hooks:
        last = (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.webhook_id == h.id)
            .order_by(WebhookDelivery.id.desc()).first()
        )
        deliveries = db.query(WebhookDelivery).filter(
            WebhookDelivery.webhook_id == h.id).count()
        data.append({
            "id": h.id, "url": h.url, "event": h.event, "active": h.active,
            "has_secret": bool(h.secret), "delivery_count": deliveries,
            "last_delivery": {
                "success": last.success, "status_code": last.status_code,
                "error": last.error,
                "created_at": last.created_at.isoformat() if last.created_at else None,
            } if last else None,
        })
    return APIResponse(data=data)


@router.post("/webhooks", summary="Register a webhook (admin)", status_code=201)
def create_webhook(
    payload: WebhookIn, db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage_thresholds")),
) -> APIResponse:
    if not payload.url.startswith(("http://", "https://")):
        raise HTTPException(422, detail={"code": "BAD_URL",
                                         "message": "URL must start with http:// or https://."})
    hook = Webhook(url=payload.url, event=payload.event, secret=payload.secret or None)
    db.add(hook)
    db.add(AuditLog(user_id=user.id, action="create_webhook", entity="webhook",
                    new_value=f"{payload.event} -> {payload.url}"))
    db.commit()
    return APIResponse(data={"id": hook.id}, message="Webhook registered.")


@router.put("/webhooks/{webhook_id}/toggle", summary="Enable/disable a webhook (admin)")
def toggle_webhook(
    webhook_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("manage_thresholds")),
) -> APIResponse:
    hook = db.get(Webhook, webhook_id)
    if not hook:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Webhook not found."})
    hook.active = not hook.active
    db.commit()
    return APIResponse(data={"id": hook.id, "active": hook.active},
                       message=f"Webhook {'enabled' if hook.active else 'disabled'}.")


@router.delete("/webhooks/{webhook_id}", summary="Delete a webhook (admin)")
def delete_webhook(
    webhook_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("manage_thresholds")),
) -> APIResponse:
    hook = db.get(Webhook, webhook_id)
    if not hook:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Webhook not found."})
    db.query(WebhookDelivery).filter(WebhookDelivery.webhook_id == webhook_id).delete()
    db.delete(hook)
    db.commit()
    return APIResponse(message="Webhook deleted.")


@router.get("/webhook-deliveries", summary="Recent webhook delivery attempts")
def webhook_deliveries(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    rows = db.query(WebhookDelivery).order_by(WebhookDelivery.id.desc()).limit(limit).all()
    return APIResponse(data=[
        {"id": d.id, "webhook_id": d.webhook_id, "document_id": d.document_id,
         "status_code": d.status_code, "success": d.success, "error": d.error,
         "created_at": d.created_at.isoformat() if d.created_at else None}
        for d in rows
    ])
