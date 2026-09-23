"""Transparent skill matching: candidate skills vs job requirements.

Two-tier, fully documented formula (surfaced with every result):

    score = w_req * (matched required / total required)
          + w_nice * (matched nice-to-have / total nice-to-have)   * 100

where w_req defaults to 0.7 and w_nice to (1 - w_req), admin-configurable at
runtime. When a job has no nice-to-have list, the score degrades cleanly to

    matched required / total required * 100

Only skills actually extracted from the candidate's document(s) participate —
nothing is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.matching import Job, SkillMatchResult
from app.models.profile import Candidate
from app.services.normalization_service import NormalizationService
from app.services.settings_service import SettingsService

FORMULA_SIMPLE = "matched required skills / total required skills * 100"
FORMULA_TIERED = (
    "w_req * matched_required/total_required + "
    "w_nice * matched_nice/total_nice, weighted * 100"
)


@dataclass
class MatchComputation:
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_nice: list[str] = field(default_factory=list)
    missing_nice: list[str] = field(default_factory=list)
    match_percentage: float = 0.0
    formula: str = FORMULA_SIMPLE


class SkillMatchingService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._normalizer = NormalizationService(db)
        self._settings = SettingsService(db)

    def compute(
        self,
        candidate_skills: list[str],
        required_skills: list[str],
        nice_to_have: list[str] | None = None,
    ) -> MatchComputation:
        aliases = self._normalizer.alias_map()
        norm = lambda s: self._normalizer.normalize_skill(s, aliases)  # noqa: E731
        cand = {s.lower() for s in self._normalizer.normalize_many(candidate_skills)}

        req = [norm(s) for s in required_skills]
        matched_req = [r for r in req if r.lower() in cand]
        missing_req = [r for r in req if r.lower() not in cand]
        req_ratio = len(matched_req) / len(req) if req else 0.0

        nice = [norm(s) for s in (nice_to_have or [])]
        if not nice:
            return MatchComputation(
                matched_skills=matched_req, missing_skills=missing_req,
                match_percentage=round(req_ratio * 100, 1),
            )
        matched_nice = [n for n in nice if n.lower() in cand]
        missing_nice = [n for n in nice if n.lower() not in cand]
        nice_ratio = len(matched_nice) / len(nice)
        w_req = float(self._settings.get("skill_match_required_weight"))
        w_nice = 1.0 - w_req
        if req:
            score = (w_req * req_ratio + w_nice * nice_ratio) * 100
        else:
            score = nice_ratio * 100
        return MatchComputation(
            matched_skills=matched_req, missing_skills=missing_req,
            matched_nice=matched_nice, missing_nice=missing_nice,
            match_percentage=round(score, 1),
            formula=f"{FORMULA_TIERED} (w_req={w_req:g}, w_nice={w_nice:g})",
        )

    def match_candidate_to_job(self, candidate: Candidate, job: Job) -> SkillMatchResult:
        comp = self.compute(
            [cs.skill.name for cs in candidate.skills],
            job.required_skills,
            job.nice_to_have_skills,
        )
        result = SkillMatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            matched_skills=comp.matched_skills,
            missing_skills=comp.missing_skills,
            matched_nice=comp.matched_nice,
            missing_nice=comp.missing_nice,
            match_percentage=comp.match_percentage,
            formula=comp.formula,
        )
        self._db.add(result)
        self._db.flush()
        self._db.refresh(result)
        return result

    def match_all_to_job(self, job: Job) -> list[SkillMatchResult]:
        candidates = self._db.query(Candidate).all()
        results = [self.match_candidate_to_job(cand, job) for cand in candidates]
        results.sort(key=lambda r: r.match_percentage, reverse=True)
        return results
