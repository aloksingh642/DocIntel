"""Skill normalization against a configurable alias dictionary.

Aliases are admin-managed through the ``skill_aliases`` table and override the
seed dictionary — no deploy required to add a synonym.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import SkillAlias
from app.services.skill_data import DEFAULT_SKILL_ALIASES, SKILL_TAXONOMY

_WS = re.compile(r"\s+")


def _canonical_form(raw: str) -> str:
    return _WS.sub(" ", raw.strip().lower())


class NormalizationService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def alias_map(self) -> dict[str, str]:
        """DB aliases first, seeded defaults as fallback."""
        aliases: dict[str, str] = dict(DEFAULT_SKILL_ALIASES)
        for row in self._db.scalars(select(SkillAlias)).all():
            aliases[_canonical_form(row.alias)] = row.canonical
        return aliases

    def normalize_skill(self, raw: str, aliases: dict[str, str] | None = None) -> str:
        """Map a raw skill mention to its canonical taxonomy name.

        'Python programming' -> 'Python', 'Postgre SQL' -> 'PostgreSQL',
        'Amazon Web Services' -> 'AWS'. Unknown skills keep a cleaned
        title-cased form rather than being dropped (no invention, no loss).
        """
        aliases = aliases or self.alias_map()
        key = _canonical_form(raw)
        if key in aliases:
            return aliases[key]
        for known in SKILL_TAXONOMY:
            if _canonical_form(known) == key:
                return known
        return raw.strip()

    def normalize_many(self, raw_skills: list[str]) -> list[str]:
        aliases = self.alias_map()
        seen: dict[str, None] = {}
        for skill in raw_skills:
            normalized = self.normalize_skill(skill, aliases)
            if normalized:
                seen[normalized] = None
        return list(seen)
