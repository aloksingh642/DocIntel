"""Document query repository. Keeps SQL out of the API layer."""
from __future__ import annotations

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.profile import Candidate


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        document_type: str | None = None,
        duplicates_only: bool = False,
        failed_only: bool = False,
    ) -> tuple[list[Document], int]:
        q = select(Document).order_by(Document.created_at.desc())
        if status:
            q = q.where(Document.processing_status == status)
        if document_type:
            q = q.where(Document.document_type == document_type)
        if duplicates_only:
            q = q.where(Document.is_duplicate.is_(True))
        if failed_only:
            q = q.where(Document.processing_status == "failed")
        total = self._db.scalar(select(func.count()).select_from(q.subquery())) or 0
        items = self._db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
        return list(items), total

    @staticmethod
    def page_dict(items: list, total: int, page: int, page_size: int) -> dict:
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, ceil(total / page_size)),
        }


class CandidateRepository:
    """Candidate search across identity, skills, education, experience, location."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def search(
        self,
        query: str | None = None,
        skill: str | None = None,
        location: str | None = None,
        degree: str | None = None,
        min_experience: float | None = None,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        tag: str | None = None,
    ) -> tuple[list[Candidate], int]:
        from app.models.profile import (
            CandidateSkill,
            CandidateTag,
            Education,
            Experience,
            Skill,
        )

        q = select(Candidate).distinct()
        if skill:
            # Multi-term skill search ("Python AWS") requires ALL terms (AND);
            # each term may match any of the candidate's skills.
            for term in skill.lower().split():
                q = q.where(
                    Candidate.id.in_(
                        select(CandidateSkill.candidate_id)
                        .join(Skill, Skill.id == CandidateSkill.skill_id)
                        .where(Skill.normalized_name.ilike(f"%{term}%"))
                    )
                )
        if location:
            q = q.where(Candidate.location.ilike(f"%{location}%"))
        if degree:
            q = q.join(Education, Education.candidate_id == Candidate.id).where(
                Education.degree.ilike(f"%{degree}%")
            )
        if min_experience is not None:
            q = q.where(Candidate.total_experience_years >= min_experience)
        if status:
            q = q.where(Candidate.status == status)
        if tag:
            q = q.where(
                Candidate.id.in_(
                    select(CandidateTag.candidate_id).where(
                        CandidateTag.tag == tag.strip().lower()
                    )
                )
            )
        if query:
            like = f"%{query}%"
            q = q.where(
                or_(
                    Candidate.name.ilike(like),
                    Candidate.email.ilike(like),
                    Candidate.id.in_(
                        select(Experience.candidate_id).where(
                            or_(
                                Experience.company.ilike(like),
                                Experience.job_title.ilike(like),
                            )
                        )
                    ),
                )
            )
        total = self._db.scalar(select(func.count()).select_from(q.subquery())) or 0
        items = self._db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
        return list(items), total
