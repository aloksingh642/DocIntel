"""Natural-language candidate search.

Answers queries like "python backend developer with docker" by embedding the
query and each candidate profile (name + skills + education + experience +
summary) into a shared TF-IDF space and ranking by cosine similarity. The
service boundary mirrors duplicate_service so a neural-embedding backend can
replace the internals later.
"""
from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Candidate

MIN_SCORE = 0.03  # below this the result carries no meaningful signal


@dataclass
class SemanticHit:
    candidate: Candidate
    score: float


class SemanticSearchService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _candidate_text(self, c: Candidate) -> str:
        parts: list[str] = [c.name or "", c.professional_summary or ""]
        parts.extend(cs.skill.name for cs in c.skills)
        parts.extend(
            " ".join(filter(None, (e.degree, e.field, e.institution))) for e in c.educations
        )
        parts.extend(
            " ".join(filter(None, (x.job_title, x.company, x.description)))
            for x in c.experiences
        )
        parts.extend(p.name + " " + (p.description or "") for p in c.projects)
        return " ".join(parts)

    def search(self, query: str, limit: int = 20) -> list[SemanticHit]:
        candidates = list(self._db.scalars(select(Candidate)).all())
        if not candidates or not query.strip():
            return []
        texts = [self._candidate_text(c) for c in candidates]
        corpus = texts + [query]
        try:
            vectors = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2), max_features=12000
            ).fit_transform(corpus)
            sims = cosine_similarity(vectors[-1], vectors[:-1])[0]
        except ValueError:
            return []
        hits = [
            SemanticHit(candidate=c, score=round(float(sims[i]), 4))
            for i, c in enumerate(candidates)
            if sims[i] >= MIN_SCORE
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
