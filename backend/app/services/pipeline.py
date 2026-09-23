"""Document processing pipeline orchestrator.

Stages (each independently timed, logged and failure-isolated):

    validate -> extract (with OCR fallback) -> classify -> ai_extract
    -> normalize -> duplicate_check -> persist -> done

Runs in a background worker (FastAPI BackgroundTasks in-process, or Celery
when REDIS_URL is configured — the task body is identical).
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import SessionLocal
from app.extractors import ExtractionError, get_extractor
from app.extractors.ocr import OCRUnavailable, tesseract_available
from app.models.document import Document, ProcessingLog, ProcessingStatus
from app.models.profile import (
    Candidate,
    CandidateSkill,
    Certification,
    Education,
    Experience,
    Project,
    Skill,
)
from app.schemas.extraction import ExtractionResult
from app.services.classification_service import ClassificationService
from app.services.duplicate_service import DuplicateService
from app.services.extraction_service import ExtractionService, ExtractionValidationError
from app.services.normalization_service import NormalizationService
from app.services.skill_data import SKILL_TAXONOMY
from app.services.webhook_service import dispatch_event

logger = logging.getLogger("idp.pipeline")


class StageFailure(Exception):
    def __init__(self, stage: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.stage = stage
        self.safe_message = safe_message


class Pipeline:
    """Stateless orchestrator; a fresh instance per document is cheap."""

    def __init__(self, db: Session, document: Document) -> None:
        self.db = db
        self.document = document
        self.classifier = ClassificationService(db)
        self.extractor = ExtractionService()
        self.normalizer = NormalizationService(db)
        self.duplicates = DuplicateService(db)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _set_status(self, status: str, error: str | None = None) -> None:
        self.document.processing_status = status
        self.document.processing_error = error
        self.db.flush()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Time a stage and persist a ProcessingLog entry either way."""
        start = time.perf_counter()
        try:
            yield
        except StageFailure as exc:
            self._log(name, "failed", exc.safe_message, time.perf_counter() - start)
            raise
        else:
            self._log(name, "success", None, time.perf_counter() - start)

    def _log(self, stage: str, status: str, message: str | None, elapsed: float | None) -> None:
        self.db.add(
            ProcessingLog(
                document_id=self.document.id,
                stage=stage,
                status=status,
                message=message[:2000] if message else None,
                processing_time=round(elapsed, 4) if elapsed is not None else None,
            )
        )
        self.db.flush()
        logger.info(
            "doc=%s stage=%s status=%s elapsed=%ss %s",
            self.document.id, stage, status,
            f"{elapsed:.3f}" if elapsed else "-", message or "",
        )

    # ------------------------------------------------------------------ #
    # main entry
    # ------------------------------------------------------------------ #
    def run(self) -> Document:
        doc = self.document
        try:
            self._set_status(ProcessingStatus.PROCESSING)

            # ---- text extraction (with OCR fallback inside extractors) ----
            self._set_status(ProcessingStatus.EXTRACTING)
            with self.stage("extract"):
                try:
                    output = get_extractor(doc.file_type).extract(Path(doc.file_path))
                except (ExtractionError, OCRUnavailable) as exc:
                    raise StageFailure("extract", str(exc)[:500]) from exc
                if not output.text.strip():
                    raise StageFailure("extract", "No text could be extracted from the document.")
                doc.extracted_text = output.text
                self._log("extract_note", "info",
                          f"used_ocr={output.used_ocr}; ocr_available={tesseract_available()}", None)

            # ---- classification ----------------------------------------
            self._set_status(ProcessingStatus.CLASSIFYING)
            with self.stage("classify"):
                classification = self.classifier.classify(doc.extracted_text)
                doc.document_type = classification.document_type
                doc.classification_confidence = classification.confidence

            # ---- AI extraction (resume only; other types stop here) ----
            result: ExtractionResult | None = None
            if classification.document_type == "resume":
                with self.stage("ai_extract"):
                    try:
                        result = self.extractor.extract_resume(doc.extracted_text)
                    except ExtractionValidationError as exc:
                        raise StageFailure("ai_extract", str(exc)) from exc
                    doc.extraction_confidence = result.confidence

            # ---- duplicate check ----------------------------------------
            self._set_status(ProcessingStatus.DUPLICATE_CHECK)
            with self.stage("duplicate_check"):
                report = self.duplicates.check_content_similarity(
                    doc.extracted_text, exclude_id=doc.id
                )
                if report.is_duplicate:
                    doc.is_duplicate = True
                    doc.duplicate_type = report.duplicate_type
                    doc.duplicate_similarity = report.similarity
                    doc.duplicate_of_id = report.matched_document_id

            # ---- persist structured profile ------------------------------
            with self.stage("persist"):
                if result is not None:
                    candidate = self._persist_candidate(result)
                    doc.candidate_id = candidate.id

            # ---- final status --------------------------------------------
            review_reasons: list[str] = []
            if self.classifier.needs_review(doc.classification_confidence):
                review_reasons.append("low classification confidence")
            if result and (result.confidence or 0) < settings.CLASSIFICATION_CONFIDENCE_THRESHOLD:
                review_reasons.append("low extraction confidence")
            if doc.is_duplicate and doc.duplicate_type == "content_similarity":
                review_reasons.append("possible duplicate content")

            doc.processed_at = datetime.now(timezone.utc)
            if review_reasons:
                self._set_status(ProcessingStatus.NEEDS_REVIEW, "; ".join(review_reasons))
            else:
                self._set_status(ProcessingStatus.COMPLETED)

        except StageFailure as exc:
            self._set_status(ProcessingStatus.FAILED, f"{exc.stage}: {exc.safe_message}")
        except Exception as exc:  # defensive: never crash the worker
            logger.exception("doc=%s unhandled pipeline error", doc.id)
            self._log("pipeline", "failed", f"Unexpected error: {exc.__class__.__name__}", None)
            self._set_status(ProcessingStatus.FAILED, f"pipeline: unexpected error ({exc.__class__.__name__})")

        # Notify subscribed webhooks about the final outcome (best-effort;
        # delivery failures are recorded, never raised).
        try:
            dispatch_event(self.db, "document.processed", {
                "document_id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "processing_status": doc.processing_status,
                "candidate_id": doc.candidate_id,
                "is_duplicate": doc.is_duplicate,
            })
        except Exception:
            logger.warning("webhook dispatch failed for doc %s", doc.id, exc_info=True)

        self.db.commit()
        self.db.refresh(doc)
        return doc

    # ------------------------------------------------------------------ #
    # persistence
    # ------------------------------------------------------------------ #
    def _persist_candidate(self, result: ExtractionResult) -> Candidate:
        """Create-or-reuse candidate (Level-2 duplicate identity), then attach
        normalized skills and structured sub-entities."""
        info = result.candidate
        candidate = self.duplicates.find_candidate(info.email, info.phone, info.name)
        if candidate is None:
            candidate = Candidate()
            self.db.add(candidate)

        # update scalars only with fresh values (never clobber with None)
        for attr in ("name", "email", "phone", "location", "linkedin", "github",
                     "portfolio", "professional_summary"):
            value = getattr(info, attr)
            if value:
                setattr(candidate, attr, str(value))
        if result.total_experience_years is not None:
            candidate.total_experience_years = result.total_experience_years
        self.db.flush()

        # skills: normalized, upserted
        for name in self.normalizer.normalize_many(result.skills):
            skill = self.db.query(Skill).filter(
                Skill.normalized_name == name.lower()
            ).first()
            if skill is None:
                skill = Skill(
                    name=name,
                    normalized_name=name.lower(),
                    category=SKILL_TAXONOMY.get(name, "other"),
                )
                self.db.add(skill)
                self.db.flush()
            if not any(cs.skill_id == skill.id for cs in candidate.skills):
                self.db.add(CandidateSkill(candidate_id=candidate.id, skill_id=skill.id))

        # experiences / education / certifications / projects
        existing_exp = {e.description for e in candidate.experiences}
        for exp in result.experiences:
            if exp.description and exp.description in existing_exp:
                continue
            self.db.add(Experience(
                candidate_id=candidate.id, company=exp.company, job_title=exp.job_title,
                description=exp.description,
            ))

        existing_edu = {(e.degree, e.field, e.end_year) for e in candidate.educations}
        for edu in result.education:
            key = (edu.degree, edu.field, edu.end_year)
            if key in existing_edu or not any(key):
                continue
            self.db.add(Education(
                candidate_id=candidate.id, institution=edu.institution, degree=edu.degree,
                field=edu.field, start_year=edu.start_year, end_year=edu.end_year,
            ))

        existing_cert = {c.name.lower() for c in candidate.certifications}
        for cert in result.certifications:
            if cert.name.lower() in existing_cert:
                continue
            self.db.add(Certification(
                candidate_id=candidate.id, name=cert.name, issuer=cert.issuer,
            ))

        existing_proj = {p.name.lower() for p in candidate.projects}
        for proj in result.projects:
            if proj.name.lower() in existing_proj:
                continue
            self.db.add(Project(
                candidate_id=candidate.id, name=proj.name, description=proj.description,
                technologies=", ".join(proj.technologies) if proj.technologies else None,
            ))
        self.db.flush()
        return candidate


# ---------------------------------------------------------------------- #
# Task entry-points (FastAPI BackgroundTasks today; Celery-compatible)    #
# ---------------------------------------------------------------------- #

def process_document_task(document_id: int) -> None:
    """Worker entry-point: owns its own DB session lifecycle."""
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.error("process_document_task: document %s not found", document_id)
            return
        Pipeline(db, document).run()
    except Exception:
        logger.exception("process_document_task failed for doc %s", document_id)
        db.rollback()
    finally:
        db.close()
