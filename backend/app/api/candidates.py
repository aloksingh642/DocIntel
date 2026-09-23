"""Candidate endpoints: list, search (multi-criteria + semantic), detail, edit,
ATS workflow (status, notes, tags), and CSV export."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_permission
from app.database.session import get_db
from app.models.document import AuditLog
from app.models.matching import SkillMatchResult
from app.models.profile import (
    Candidate,
    CandidateNote,
    CandidateSkill,
    CandidateStatus,
    CandidateTag,
    Skill,
)
from app.models.user import User
from app.repositories.document_repository import CandidateRepository, DocumentRepository
from app.schemas.api import CandidateUpdate, NoteIn, StatusChange, TagIn
from app.schemas.common import APIResponse
from app.services.normalization_service import NormalizationService
from app.services.semantic_search_service import SemanticSearchService

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _summary(c: Candidate) -> dict:
    return {
        "id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
        "location": c.location,
        "total_experience_years": c.total_experience_years,
        "skills": sorted({cs.skill.name for cs in c.skills}),
        "status": c.status,
        "tags": sorted({t.tag for t in c.tags}),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ------------------------------ read endpoints ------------------------------ #


@router.get("", summary="List candidates (paginated)")
def list_candidates(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    repo = CandidateRepository(db)
    items, total = repo.search(page=page, page_size=page_size, status=status_filter)
    return APIResponse(
        data=DocumentRepository.page_dict([_summary(c) for c in items], total, page, page_size)
    )


@router.get("/search", summary="Search candidates",
            description="Structured search: q (name/email/company/title), one or more "
            "skills (AND), location, degree, min experience, status and tag.")
def search_candidates(
    q: str | None = None,
    skill: str | None = None,
    location: str | None = None,
    degree: str | None = None,
    min_experience: float | None = None,
    status: str | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    repo = CandidateRepository(db)
    items, total = repo.search(q, skill, location, degree, min_experience, page,
                               page_size, status=status, tag=tag)
    return APIResponse(
        data=DocumentRepository.page_dict([_summary(c) for c in items], total, page, page_size)
    )


@router.get("/semantic-search", summary="Natural-language candidate search",
            description="Ranks candidates by cosine similarity between the free-text "
            "query and their full profile (skills, experience, education, projects).")
def semantic_search(
    q: str = Query(min_length=2),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    hits = SemanticSearchService(db).search(q, limit)
    return APIResponse(data=[
        {**_summary(hit.candidate), "score": hit.score} for hit in hits
    ])


@router.get("/export.csv", summary="Export candidates as CSV",
            description="Honours the same filters as /search. Produces a spreadsheet-"
            "friendly UTF-8 CSV.")
def export_candidates_csv(
    q: str | None = None,
    skill: str | None = None,
    location: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> StreamingResponse:
    repo = CandidateRepository(db)
    items, _ = repo.search(q, skill, location, page=1, page_size=10_000,
                           status=status, tag=tag)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "email", "phone", "location", "experience_years",
                     "skills", "status", "tags", "documents", "created_at"])
    for c in items:
        writer.writerow([
            c.id, c.name or "", c.email or "", c.phone or "", c.location or "",
            c.total_experience_years if c.total_experience_years is not None else "",
            "; ".join(sorted({cs.skill.name for cs in c.skills})),
            c.status, "; ".join(sorted({t.tag for t in c.tags})),
            len(c.documents),
            c.created_at.isoformat() if c.created_at else "",
        ])
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=candidates_export.csv"}
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers
    )


@router.get("/{candidate_id}", summary="Candidate profile")
def get_candidate(
    candidate_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    cand = (
        db.query(Candidate)
        .options(
            joinedload(Candidate.skills).joinedload(CandidateSkill.skill),
            joinedload(Candidate.experiences), joinedload(Candidate.educations),
            joinedload(Candidate.certifications), joinedload(Candidate.projects),
            joinedload(Candidate.notes), joinedload(Candidate.tags),
        )
        .filter(Candidate.id == candidate_id)
        .first()
    )
    if not cand:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})

    matches = (
        db.query(SkillMatchResult)
        .filter(SkillMatchResult.candidate_id == candidate_id)
        .order_by(SkillMatchResult.created_at.desc()).limit(20).all()
    )
    documents = [
        {"id": d.id, "filename": d.filename, "document_type": d.document_type,
         "processing_status": d.processing_status}
        for d in cand.documents
    ]
    data = _summary(cand)
    data.update({
        "linkedin": cand.linkedin, "github": cand.github, "portfolio": cand.portfolio,
        "professional_summary": cand.professional_summary,
        "experiences": [{"id": e.id, "company": e.company, "job_title": e.job_title,
                         "description": e.description} for e in cand.experiences],
        "education": [{"id": e.id, "institution": e.institution, "degree": e.degree,
                       "field": e.field, "end_year": e.end_year} for e in cand.educations],
        "certifications": [{"id": c.id, "name": c.name, "issuer": c.issuer}
                           for c in cand.certifications],
        "projects": [{"id": p.id, "name": p.name, "description": p.description,
                      "technologies": p.technologies} for p in cand.projects],
        "notes": [{"id": n.id, "text": n.text, "user_id": n.user_id,
                   "created_at": n.created_at.isoformat() if n.created_at else None}
                  for n in sorted(cand.notes, key=lambda n: n.created_at, reverse=True)],
        "documents": documents,
        "skill_matches": [{"job_id": m.job_id, "match_percentage": m.match_percentage,
                           "matched_skills": m.matched_skills, "missing_skills": m.missing_skills}
                          for m in matches],
    })
    return APIResponse(data=data)


@router.put("/{candidate_id}", summary="Edit candidate (human correction)",
            description="Corrections are audited with old/new values, per the human-review rules.")
def update_candidate(
    candidate_id: int, payload: CandidateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("review")),
) -> APIResponse:
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})

    changes: list[str] = []
    for field in ("name", "email", "phone", "location", "linkedin", "github",
                  "portfolio", "professional_summary", "total_experience_years"):
        value = getattr(payload, field, None)
        if value is not None:
            old = getattr(cand, field)
            if old != value:
                changes.append(f"{field}: {old!r} -> {value!r}")
                setattr(cand, field, str(value) if not isinstance(value, (int, float)) else value)

    if payload.skills is not None:
        normalizer = NormalizationService(db)
        cand.skills.clear()
        db.flush()
        for name in normalizer.normalize_many(payload.skills):
            skill = db.query(Skill).filter(Skill.normalized_name == name.lower()).first()
            if not skill:
                skill = Skill(name=name, normalized_name=name.lower(), category="other")
                db.add(skill)
                db.flush()
            db.add(CandidateSkill(candidate_id=cand.id, skill_id=skill.id))
        changes.append("skills replaced")

    if changes:
        db.add(AuditLog(user_id=user.id, action="edit_candidate", entity="candidate",
                        entity_id=cand.id, new_value="; ".join(changes)))
    db.commit()
    return APIResponse(data=_summary(cand), message="Candidate updated.")


# ---------------------------- ATS workflow ---------------------------------- #


@router.put("/{candidate_id}/status", summary="Move candidate through the pipeline",
            description="Stages: new → reviewing → shortlisted → interviewed → offer → "
            "hired (or rejected at any point). Audited.")
def change_status(
    candidate_id: int, payload: StatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("review")),
) -> APIResponse:
    if payload.status not in CandidateStatus.ALL:
        raise HTTPException(400, detail={"code": "BAD_STATUS",
                                         "message": f"Status must be one of {CandidateStatus.ALL}."})
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    old = cand.status
    cand.status = payload.status
    db.add(AuditLog(user_id=user.id, action="candidate_status", entity="candidate",
                    entity_id=cand.id, old_value=old, new_value=payload.status))
    db.commit()
    return APIResponse(data={"id": cand.id, "status": cand.status},
                       message=f"Status changed {old} -> {payload.status}.")


@router.post("/{candidate_id}/notes", summary="Add a recruiter note", status_code=201)
def add_note(
    candidate_id: int, payload: NoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("review")),
) -> APIResponse:
    if not db.get(Candidate, candidate_id):
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    note = CandidateNote(candidate_id=candidate_id, user_id=user.id, text=payload.text.strip())
    db.add(note)
    db.commit()
    return APIResponse(
        data={"id": note.id, "text": note.text, "user_id": note.user_id,
              "created_at": note.created_at.isoformat()},
        message="Note added.",
    )


@router.delete("/{candidate_id}/notes/{note_id}", summary="Delete a note")
def delete_note(
    candidate_id: int, note_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("review")),
) -> APIResponse:
    note = db.get(CandidateNote, note_id)
    if not note or note.candidate_id != candidate_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Note not found."})
    db.delete(note)
    db.commit()
    return APIResponse(message="Note deleted.")


@router.post("/{candidate_id}/tags", summary="Tag a candidate", status_code=201)
def add_tag(
    candidate_id: int, payload: TagIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("review")),
) -> APIResponse:
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Candidate not found."})
    tag = " ".join(payload.tag.strip().lower().split())[:64]
    if not tag:
        raise HTTPException(422, detail={"code": "EMPTY_TAG", "message": "Tag cannot be empty."})
    if not any(t.tag == tag for t in cand.tags):
        db.add(CandidateTag(candidate_id=candidate_id, tag=tag))
        db.commit()
    return APIResponse(data={"tags": sorted({t.tag for t in cand.tags} | {tag})},
                       message="Tag added.")


@router.delete("/{candidate_id}/tags/{tag}", summary="Remove a tag")
def remove_tag(
    candidate_id: int, tag: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("review")),
) -> APIResponse:
    row = db.get(CandidateTag, (candidate_id, tag))
    if row:
        db.delete(row)
        db.commit()
    return APIResponse(message="Tag removed.")
