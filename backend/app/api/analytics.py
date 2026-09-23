"""Analytics endpoints powering the dashboard charts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", summary="Headline metrics")
def overview(db: Session = Depends(get_db), _: User = Depends(require_permission("read"))) -> APIResponse:
    return APIResponse(data=AnalyticsService(db).overview())


@router.get("/documents", summary="Document analytics (type, status, uploads over time)")
def documents(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db), _: User = Depends(require_permission("read")),
) -> APIResponse:
    svc = AnalyticsService(db)
    return APIResponse(data={
        "by_type": svc.documents_by_type(),
        "by_status": svc.processing_status_breakdown(),
        "uploads_over_time": svc.uploads_over_time(days),
    })


@router.get("/skills", summary="Skill distribution across candidates")
def skills(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), _: User = Depends(require_permission("read")),
) -> APIResponse:
    return APIResponse(data=AnalyticsService(db).skill_distribution(limit))


@router.get("/candidates", summary="Candidate analytics")
def candidates(db: Session = Depends(get_db), _: User = Depends(require_permission("read"))) -> APIResponse:
    svc = AnalyticsService(db)
    return APIResponse(data={
        "experience_distribution": svc.experience_distribution(),
        "education_distribution": svc.education_distribution(),
        "location_distribution": svc.location_distribution(),
        "recent_matches": svc.recent_matches(),
    })
