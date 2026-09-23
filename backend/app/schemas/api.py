"""Request/response schemas for the REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

# ------------------------------- Auth ---------------------------------------


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="viewer")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# ------------------------------- Documents ----------------------------------


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    document_type: str | None
    classification_confidence: float | None
    extraction_confidence: float | None
    processing_status: str
    processing_error: str | None
    is_duplicate: bool
    duplicate_type: str | None
    duplicate_similarity: float | None
    duplicate_of_id: int | None
    candidate_id: int | None
    created_at: datetime | None
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class ProcessingLogOut(BaseModel):
    id: int
    stage: str
    status: str
    message: str | None
    processing_time: float | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ClassificationOut(BaseModel):
    document_type: str | None
    confidence: float | None


class ExtractionPayloadOut(BaseModel):
    """Explainability-friendly view of extracted candidate data."""

    candidate: dict[str, Any] | None
    skills: list[str] = []
    experiences: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    certifications: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    languages: list[dict[str, Any]] = []
    total_experience_years: float | None = None
    field_sources: dict[str, str] = {}


# ------------------------------- Candidates ---------------------------------


class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    professional_summary: str | None = None
    total_experience_years: float | None = None
    skills: list[str] | None = None


# ------------------------------- ATS workflow -------------------------------


class StatusChange(BaseModel):
    status: str


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TagIn(BaseModel):
    tag: str = Field(min_length=1, max_length=64)


# ------------------------------- Skills / Jobs ------------------------------


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category: str | None = None


class SkillAliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=128)
    canonical: str = Field(min_length=1, max_length=128)


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    required_skills: list[str] = Field(min_length=1)
    nice_to_have_skills: list[str] = Field(default_factory=list)


class MatchResultOut(BaseModel):
    candidate_id: int
    candidate_name: str | None
    match_percentage: float
    matched_skills: list[str]
    missing_skills: list[str]
    matched_nice: list[str] = []
    missing_nice: list[str] = []
    formula: str


# ------------------------------- Admin / ops --------------------------------


class SettingsUpdate(BaseModel):
    values: dict[str, float]


class WebhookIn(BaseModel):
    url: str = Field(min_length=8, max_length=1024)
    event: str = Field(default="document.processed")
    secret: str | None = Field(default=None, max_length=255)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ------------------------------- Review -------------------------------------


class ReviewAction(BaseModel):
    action: str  # approve | reject
    notes: str | None = None
