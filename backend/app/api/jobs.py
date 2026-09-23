"""Skills, aliases, jobs and matching endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database.session import get_db
from app.models.document import AuditLog
from app.models.matching import Job, SkillMatchResult
from app.models.profile import CandidateSkill, Skill, SkillAlias
from app.models.user import User
from app.schemas.api import JobCreate, MatchResultOut, SkillAliasIn, SkillCreate
from app.schemas.common import APIResponse
from app.services.normalization_service import NormalizationService
from app.services.skill_matching_service import SkillMatchingService

router = APIRouter(tags=["skills & jobs"])


# ------------------------------- Skills ---------------------------------------


@router.get("/skills", summary="List skills (filterable by category)")
def list_skills(
    category: str | None = None, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    q = db.query(Skill)
    if category:
        q = q.filter(Skill.category == category)
    skills = q.order_by(Skill.name).all()
    return APIResponse(data=[
        {"id": s.id, "name": s.name, "category": s.category,
         "candidate_count": db.query(CandidateSkill).filter(CandidateSkill.skill_id == s.id).count()}
        for s in skills
    ])


@router.post("/skills", summary="Create a skill", status_code=201)
def create_skill(
    payload: SkillCreate, db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage_skills")),
) -> APIResponse:
    name = payload.name.strip()
    if db.query(Skill).filter(Skill.normalized_name == name.lower()).first():
        raise HTTPException(409, detail={"code": "EXISTS", "message": "Skill already exists."})
    skill = Skill(name=name, normalized_name=name.lower(), category=payload.category)
    db.add(skill)
    db.add(AuditLog(user_id=user.id, action="create_skill", entity="skill", new_value=name))
    db.commit()
    return APIResponse(data={"id": skill.id, "name": skill.name}, message="Skill created.")


@router.get("/skills/aliases", summary="List skill aliases")
def list_aliases(
    db: Session = Depends(get_db), _: User = Depends(require_permission("read")),
) -> APIResponse:
    aliases = db.query(SkillAlias).order_by(SkillAlias.alias).all()
    return APIResponse(data=[{"id": a.id, "alias": a.alias, "canonical": a.canonical}
                             for a in aliases])


@router.post("/skills/aliases", summary="Add/update a skill alias (admin)",
             status_code=201)
def upsert_alias(
    payload: SkillAliasIn, db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage_aliases")),
) -> APIResponse:
    key = " ".join(payload.alias.strip().lower().split())
    row = db.query(SkillAlias).filter(SkillAlias.alias == key).first()
    if row:
        row.canonical = payload.canonical.strip()
        msg = "Alias updated."
    else:
        row = SkillAlias(alias=key, canonical=payload.canonical.strip())
        db.add(row)
        msg = "Alias created."
    db.add(AuditLog(user_id=user.id, action="upsert_alias", entity="skill_alias",
                    new_value=f"{key} -> {row.canonical}"))
    db.commit()
    return APIResponse(data={"id": row.id, "alias": row.alias, "canonical": row.canonical},
                       message=msg)


# ------------------------------- Jobs -----------------------------------------


@router.post("/jobs", summary="Create a job requirement", status_code=201)
def create_job(
    payload: JobCreate, db: Session = Depends(get_db),
    user: User = Depends(require_permission("manage_jobs")),
) -> APIResponse:
    normalizer = NormalizationService(db)
    job = Job(
        title=payload.title.strip(),
        description=payload.description,
        required_skills=normalizer.normalize_many(payload.required_skills),
        nice_to_have_skills=normalizer.normalize_many(payload.nice_to_have_skills),
    )
    db.add(job)
    db.add(AuditLog(user_id=user.id, action="create_job", entity="job",
                    new_value=job.title))
    db.commit()
    db.refresh(job)
    return APIResponse(data=_job_out(job), message="Job created.")


@router.get("/jobs", summary="List jobs")
def list_jobs(
    db: Session = Depends(get_db), _: User = Depends(require_permission("read")),
) -> APIResponse:
    return APIResponse(data=[_job_out(j) for j in db.query(Job).order_by(Job.id.desc()).all()])


@router.get("/jobs/{job_id}", summary="Job detail")
def get_job(
    job_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Job not found."})
    return APIResponse(data=_job_out(job))


@router.post("/jobs/{job_id}/match", summary="Match candidates against this job",
             description="Computes and stores match results for every candidate using "
             "the transparent formula: matched/required*100.")
def match_job(
    job_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("match")),
) -> APIResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Job not found."})
    service = SkillMatchingService(db)
    results = service.match_all_to_job(job)
    db.commit()
    return APIResponse(
        data=[_match_out(r) for r in results],
        message=f"Matched {len(results)} candidate(s) against '{job.title}'.",
    )


@router.get("/jobs/{job_id}/matches", summary="Latest match results for a job")
def job_matches(
    job_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Job not found."})
    # latest result per candidate
    rows = (
        db.query(SkillMatchResult)
        .filter(SkillMatchResult.job_id == job_id)
        .order_by(SkillMatchResult.created_at.desc())
        .all()
    )
    seen, latest = set(), []
    for r in rows:
        if r.candidate_id not in seen:
            seen.add(r.candidate_id)
            latest.append(r)
    latest.sort(key=lambda r: r.match_percentage, reverse=True)
    return APIResponse(data=[_match_out(r) for r in latest])


def _job_out(job: Job) -> dict:
    return {
        "id": job.id, "title": job.title, "description": job.description,
        "required_skills": job.required_skills,
        "nice_to_have_skills": job.nice_to_have_skills,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _match_out(r: SkillMatchResult) -> dict:
    return MatchResultOut(
        candidate_id=r.candidate_id,
        candidate_name=r.candidate.name if r.candidate else None,
        match_percentage=r.match_percentage,
        matched_skills=r.matched_skills,
        missing_skills=r.missing_skills,
        matched_nice=r.matched_nice or [],
        missing_nice=r.missing_nice or [],
        formula=r.formula,
    ).model_dump(mode="json")
