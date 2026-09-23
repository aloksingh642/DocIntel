"""Candidate profile models: candidate, skills, experience, education, etc."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CandidateStatus:
    """Lightweight ATS pipeline stages for a candidate."""

    NEW = "new"
    REVIEWING = "reviewing"
    SHORTLISTED = "shortlisted"
    INTERVIEWED = "interviewed"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"

    ALL = [NEW, REVIEWING, SHORTLISTED, INTERVIEWED, OFFER, HIRED, REJECTED]


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    linkedin: Mapped[str | None] = mapped_column(String(512), nullable=True)
    github: Mapped[str | None] = mapped_column(String(512), nullable=True)
    portfolio: Mapped[str | None] = mapped_column(String(512), nullable=True)
    professional_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=CandidateStatus.NEW, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    experiences: Mapped[list["Experience"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    educations: Mapped[list["Education"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    notes: Mapped[list["CandidateNote"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    tags: Mapped[list["CandidateTag"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="candidate")  # noqa: F821


class CandidateNote(Base):
    """Recruiter notes attached to a candidate, with author and timestamp."""

    __tablename__ = "candidate_notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    candidate: Mapped[Candidate] = relationship(back_populates="notes")


class CandidateTag(Base):
    """Free-form tags for grouping/filtering candidates (e.g. 'urgent', 'remote')."""

    __tablename__ = "candidate_tags"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(64), primary_key=True)

    candidate: Mapped[Candidate] = relationship(back_populates="tags")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    normalized_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    proficiency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    years_of_experience: Mapped[float | None] = mapped_column(Float, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship()


class SkillAlias(Base):
    """Admin-managed synonym dictionary, editable without code changes."""

    __tablename__ = "skill_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alias: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    canonical: Mapped[str] = mapped_column(String(128), index=True)


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    company: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="experiences")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="educations")


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="certifications")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated

    candidate: Mapped[Candidate] = relationship(back_populates="projects")
