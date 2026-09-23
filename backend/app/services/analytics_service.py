"""Analytics aggregations for the dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, ProcessingLog, ProcessingStatus
from app.models.matching import Job, SkillMatchResult
from app.models.profile import Candidate, CandidateSkill, Education, Skill


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def overview(self) -> dict:
        docs = self._db.scalars(select(Document)).all()
        total = len(docs)
        processed = sum(1 for d in docs if d.processing_status == ProcessingStatus.COMPLETED)
        failed = sum(1 for d in docs if d.processing_status == ProcessingStatus.FAILED)
        review = sum(1 for d in docs if d.processing_status == ProcessingStatus.NEEDS_REVIEW)
        duplicates = sum(1 for d in docs if d.is_duplicate)
        total_candidates = self._db.scalar(select(func.count(Candidate.id))) or 0
        avg_time = self._db.scalar(
            select(func.avg(ProcessingLog.processing_time)).where(
                ProcessingLog.stage.in_(["extract", "classify", "ai_extract", "persist"])
            )
        )
        return {
            "total_documents": total,
            "processed_documents": processed,
            "failed_documents": failed,
            "needs_review_documents": review,
            "total_candidates": total_candidates,
            "duplicate_documents": duplicates,
            "average_stage_time_seconds": round(float(avg_time), 3) if avg_time else None,
            "total_jobs": self._db.scalar(select(func.count(Job.id))) or 0,
            "total_skills": self._db.scalar(select(func.count(Skill.id))) or 0,
        }

    def documents_by_type(self) -> list[dict]:
        rows = self._db.execute(
            select(Document.document_type, func.count()).group_by(Document.document_type)
        ).all()
        return [{"type": t or "unclassified", "count": c} for t, c in rows]

    def processing_status_breakdown(self) -> list[dict]:
        rows = self._db.execute(
            select(Document.processing_status, func.count()).group_by(
                Document.processing_status
            )
        ).all()
        return [{"status": s, "count": c} for s, c in rows]

    def uploads_over_time(self, days: int = 30) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        docs = self._db.scalars(select(Document).where(Document.created_at >= since)).all()
        per_day: dict[str, int] = {}
        for d in docs:
            key = d.created_at.strftime("%Y-%m-%d") if d.created_at else "unknown"
            per_day[key] = per_day.get(key, 0) + 1
        return [{"date": k, "count": v} for k, v in sorted(per_day.items())]

    def skill_distribution(self, limit: int = 20) -> list[dict]:
        rows = self._db.execute(
            select(Skill.name, func.count(CandidateSkill.candidate_id).label("n"))
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .group_by(Skill.name)
            .order_by(func.count(CandidateSkill.candidate_id).desc())
            .limit(limit)
        ).all()
        return [{"skill": name, "count": n} for name, n in rows]

    def experience_distribution(self) -> list[dict]:
        buckets = {"0-1": 0, "1-3": 0, "3-5": 0, "5-10": 0, "10+": 0, "unknown": 0}
        for (years,) in self._db.execute(
            select(Candidate.total_experience_years)
        ).all():
            if years is None:
                buckets["unknown"] += 1
            elif years < 1:
                buckets["0-1"] += 1
            elif years < 3:
                buckets["1-3"] += 1
            elif years < 5:
                buckets["3-5"] += 1
            elif years < 10:
                buckets["5-10"] += 1
            else:
                buckets["10+"] += 1
        return [{"bucket": k, "count": v} for k, v in buckets.items()]

    def education_distribution(self) -> list[dict]:
        rows = self._db.execute(
            select(Education.degree, func.count()).group_by(Education.degree)
        ).all()
        return [{"degree": d or "unknown", "count": c} for d, c in rows]

    def location_distribution(self) -> list[dict]:
        rows = self._db.execute(
            select(Candidate.location, func.count()).group_by(Candidate.location)
        ).all()
        return [{"location": loc or "unknown", "count": c} for loc, c in rows]

    def recent_matches(self, limit: int = 10) -> list[dict]:
        rows = self._db.scalars(
            select(SkillMatchResult).order_by(SkillMatchResult.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "candidate_id": r.candidate_id,
                "job_id": r.job_id,
                "match_percentage": r.match_percentage,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
