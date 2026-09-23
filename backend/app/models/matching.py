"""Job and skill match result models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Higher-priority "nice to have" tier; scoring formula:
    #   score = w_req * matched_required/total_required
    #         + w_nice * matched_nice/total_nice   (weights default 0.7 / 0.3)
    nice_to_have_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    matches: Mapped[list["SkillMatchResult"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class SkillMatchResult(Base):
    __tablename__ = "skill_match_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    matched_nice: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_nice: Mapped[list[str]] = mapped_column(JSON, default=list)
    match_percentage: Mapped[float] = mapped_column(Float)
    formula: Mapped[str] = mapped_column(String(255), default="matched/required*100")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    candidate: Mapped["Candidate"] = relationship()  # noqa: F821
    job: Mapped[Job] = relationship(back_populates="matches")
