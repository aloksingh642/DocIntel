"""Pydantic contracts for AI-produced structured output.

Every AI response is validated against these schemas. Missing scalar fields are
``None``; missing lists are ``[]``. The AI layer must never invent data.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class CandidateInfo(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    professional_summary: str | None = None

    # Validate email loosely at extraction time — some resumes have typos;
    # we accept syntactically plausible strings and re-validate downstream.
    @field_validator("email", mode="before")
    @classmethod
    def _allow_loose_email(cls, v):
        if isinstance(v, str) and "@" not in v:
            raise ValueError("invalid email")
        return v


class ExperienceItem(BaseModel):
    company: str | None = None
    job_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationItem(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class CertificationItem(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: str | None = None


class ProjectItem(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class LanguageItem(BaseModel):
    language: str
    proficiency: str | None = None


class DocumentClassification(BaseModel):
    document_type: Literal[
        "resume", "invoice", "contract", "purchase_order", "certificate", "other"
    ]
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """Top-level structured result produced by the extraction provider."""

    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    skills: list[str] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    total_experience_years: float | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)  # explainability
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
