"""Outbound webhook delivery with per-attempt delivery records.

Fires on pipeline events (currently: document.processed). Delivery is
synchronous-but-capped (5s timeout) and never raises — a webhook outage must
never break document processing. Failures are recorded in webhook_deliveries
for observability and future retry.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ops import Webhook, WebhookDelivery

logger = logging.getLogger("idp.webhooks")

TIMEOUT = 5.0


def _signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def dispatch_event(db: Session, event: str, payload: dict) -> int:
    """POST ``payload`` to every active webhook subscribed to ``event``.

    Returns the number of delivery attempts.
    """
    hooks = list(
        db.scalars(
            select(Webhook).where(Webhook.active.is_(True), Webhook.event == event)
        ).all()
    )
    if not hooks:
        return 0
    body = json.dumps({"event": event, "data": payload}).encode()
    attempts = 0
    for hook in hooks:
        headers = {"Content-Type": "application/json"}
        if hook.secret:
            headers["X-IDP-Signature"] = _signature(hook.secret, body)
        delivery = WebhookDelivery(
            webhook_id=hook.id, document_id=payload.get("document_id"),
            payload=body.decode()[:4000],
        )
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = client.post(hook.url, content=body, headers=headers)
            delivery.status_code = resp.status_code
            delivery.success = 200 <= resp.status_code < 300
            if not delivery.success:
                delivery.error = f"HTTP {resp.status_code}"
        except Exception as exc:  # network/timeout/DNS — record, don't raise
            delivery.error = f"{exc.__class__.__name__}: {exc}"[:500]
            logger.warning("webhook %s delivery failed: %s", hook.id, delivery.error)
        db.add(delivery)
        attempts += 1
    db.flush()
    return attempts
