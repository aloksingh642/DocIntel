"""Runtime configuration with database-backed overrides.

Admins change thresholds from the UI (`AppSetting` rows); unset keys fall
back to environment configuration. No redeploy required.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as env
from app.models.ops import AppSetting

TUNABLES: dict[str, dict] = {
    "classification_confidence_threshold": {
        "type": float, "default": env.CLASSIFICATION_CONFIDENCE_THRESHOLD,
        "min": 0.0, "max": 1.0,
        "label": "Classification confidence threshold",
        "help": "Below this score documents are routed to needs_review.",
    },
    "duplicate_similarity_threshold": {
        "type": float, "default": env.DUPLICATE_SIMILARITY_THRESHOLD,
        "min": 0.5, "max": 1.0,
        "label": "Duplicate similarity threshold",
        "help": "Content similarity above this value flags a possible duplicate.",
    },
    "skill_match_required_weight": {
        "type": float, "default": 0.7,
        "min": 0.0, "max": 1.0,
        "label": "Required-skills weight in matching",
        "help": "Share of the match score assigned to required skills (rest goes to nice-to-have).",
    },
}


class SettingsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, key: str):
        spec = TUNABLES[key]
        row = self._db.scalars(
            select(AppSetting).where(AppSetting.key == key)
        ).first()
        if row is None:
            return spec["default"]
        try:
            return spec["type"](row.value)
        except (TypeError, ValueError):
            return spec["default"]

    def set(self, key: str, raw, user_id: int | None):
        spec = TUNABLES.get(key)
        if spec is None:
            raise ValueError(f"Unknown setting '{key}'.")
        value = spec["type"](raw)
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and value < lo or hi is not None and value > hi:
            raise ValueError(f"'{key}' must be between {lo} and {hi}.")
        row = self._db.scalars(select(AppSetting).where(AppSetting.key == key)).first()
        if row is None:
            self._db.add(AppSetting(key=key, value=str(value), updated_by=user_id))
        else:
            row.value = str(value)
            row.updated_by = user_id
        self._db.flush()
        return value

    def all_current(self) -> list[dict]:
        stored = {r.key: r for r in self._db.scalars(select(AppSetting)).all()}
        out = []
        for key, spec in TUNABLES.items():
            row = stored.get(key)
            out.append({
                "key": key,
                "value": self.get(key),
                "default": spec["default"],
                "label": spec["label"],
                "help": spec["help"],
                "overridden": row is not None,
                "min": spec.get("min"),
                "max": spec.get("max"),
            })
        return out
