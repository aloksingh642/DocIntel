"""Three-level duplicate detection.

Level 1 — exact file duplicate: SHA-256 hash comparison.
Level 2 — candidate duplicate: normalized email / phone / name identity.
Level 3 — content similarity: TF-IDF embeddings + cosine similarity above a
          configurable threshold. Suspected duplicates are FLAGGED, never
          auto-deleted, and surfaced for human review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.profile import Candidate
from app.services.settings_service import SettingsService


@dataclass
class DuplicateReport:
    is_duplicate: bool = False
    duplicate_type: str | None = None          # exact_file | candidate_identity | content_similarity
    similarity: float | None = None
    matched_document_id: int | None = None
    matched_candidate_id: int | None = None


def normalize_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits or None


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"\s+", " ", name.strip().lower()) or None


class DuplicateService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # Level 1 -------------------------------------------------------------- #
    def check_exact_file(self, file_hash: str, exclude_id: int | None = None) -> DuplicateReport:
        q = select(Document).where(Document.file_hash == file_hash)
        if exclude_id:
            q = q.where(Document.id != exclude_id)
        other = self._db.scalars(q).first()
        if other:
            return DuplicateReport(
                is_duplicate=True,
                duplicate_type="exact_file",
                similarity=1.0,
                matched_document_id=other.id,
                matched_candidate_id=other.candidate_id,
            )
        return DuplicateReport()

    # Level 2 -------------------------------------------------------------- #
    def find_candidate(
        self, email: str | None, phone: str | None, name: str | None
    ) -> Candidate | None:
        """Match on normalized identity: email first, then phone, then name."""
        n_email, n_phone, n_name = (
            normalize_email(email), normalize_phone(phone), normalize_name(name)
        )
        for cand in self._db.scalars(select(Candidate)).all():
            if n_email and normalize_email(cand.email) == n_email:
                return cand
            if n_phone and normalize_phone(cand.phone) == n_phone:
                return cand
            if n_name and normalize_name(cand.name) == n_name and (cand.email or cand.phone):
                return cand
        return None

    # Level 3 -------------------------------------------------------------- #
    def check_content_similarity(
        self, text: str, exclude_id: int | None = None
    ) -> DuplicateReport:
        docs = [
            d
            for d in self._db.scalars(
                select(Document).where(Document.extracted_text.isnot(None))
            ).all()
            if d.id != exclude_id and d.extracted_text
        ]
        if not docs or not text.strip():
            return DuplicateReport()
        corpus: list[str] = [d.extracted_text or "" for d in docs] + [text]
        try:
            vectors = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2), max_features=8000
            ).fit_transform(corpus)
            sims = cosine_similarity(vectors[-1], vectors[:-1])[0]
        except ValueError:
            return DuplicateReport()  # degenerate corpus (e.g. all stopwords)
        best_idx = int(sims.argmax())
        best = float(sims[best_idx])
        # Runtime-configurable threshold (admin settings override env default)
        threshold = SettingsService(self._db).get("duplicate_similarity_threshold")
        if best >= threshold:
            other = docs[best_idx]
            return DuplicateReport(
                is_duplicate=True,
                duplicate_type="content_similarity",
                similarity=round(best, 4),
                matched_document_id=other.id,
                matched_candidate_id=other.candidate_id,
            )
        return DuplicateReport(similarity=round(best, 4))
