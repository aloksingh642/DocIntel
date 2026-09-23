"""Document classification with a configurable confidence threshold.

confidence >= threshold  -> automatically classified
confidence <  threshold  -> document is routed to ``needs_review``
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.factory import get_llm_provider
from app.config import settings
from app.schemas.extraction import DocumentClassification
from app.services.settings_service import SettingsService


class ClassificationService:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def classify(self, text: str) -> DocumentClassification:
        return get_llm_provider().classify_document(text)

    def needs_review(self, confidence: float | None) -> bool:
        """Threshold may be overridden at runtime by admins (DB-backed)."""
        if self._db is not None:
            threshold = SettingsService(self._db).get("classification_confidence_threshold")
        else:
            threshold = settings.CLASSIFICATION_CONFIDENCE_THRESHOLD
        return confidence is None or confidence < threshold
