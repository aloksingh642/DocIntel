"""Evaluate extraction quality against the sample dataset's expected outputs.

Reports per-field accuracy and skill precision/recall/F1 — the measurable
quality gate from section 34 of the spec. Run:

    python scripts/evaluate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.factory import get_llm_provider          # noqa: E402
from app.services.normalization_service import NormalizationService  # noqa: E402
from app.services.skill_data import DEFAULT_SKILL_ALIASES  # noqa: E402

DATASET = Path(__file__).resolve().parents[2] / "sample_dataset"


def norm_skills(skills: list[str]) -> set[str]:
    return {DEFAULT_SKILL_ALIASES.get(s.lower(), s).lower() for s in skills}


def main() -> int:
    provider = get_llm_provider("mock")
    expected = json.loads((DATASET / "expected_outputs.json").read_text())

    field_hits = {k: [0, 0] for k in ("name", "email", "phone", "years", "degree")}
    total_tp = total_fp = total_fn = 0

    print(f"{'file':32} {'name':5} {'email':6} {'phone':6} {'years':6} {'deg':4} {'skill-P/R/F1'}")
    for filename, exp in expected.items():
        text = (DATASET / filename.replace(".pdf", ".txt").replace(".docx", ".txt")).read_text()
        result = provider.extract_resume(text)
        c = result.candidate
        checks = {
            "name": (c.name or "").lower() == exp["name"].lower(),
            "email": (c.email or "").lower() == exp["email"].lower(),
            "phone": "".join(filter(str.isdigit, c.phone or ""))[-10:]
                     == "".join(filter(str.isdigit, exp["phone"]))[-10:],
            "years": result.total_experience_years == exp["years"],
            "degree": any((e.degree or "") == exp["degree"] for e in result.education),
        }
        for k, ok in checks.items():
            field_hits[k][0] += int(ok)
            field_hits[k][1] += 1

        got, want = norm_skills(result.skills), norm_skills(exp["skills"])
        tp, fp, fn = len(got & want), len(got - want), len(want - got)
        total_tp += tp; total_fp += fp; total_fn += fn
        p = tp / (tp + fp) if tp + fp else 1.0
        r = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        row = " ".join(f"{str(checks[k])[:1]:>{w}}" for k, w in
                       (("name", 5), ("email", 6), ("phone", 6), ("years", 6), ("degree", 4)))
        print(f"{filename:32} {row} {p:.2f}/{r:.2f}/{f1:.2f}")

    print("-" * 80)
    for k, (hit, tot) in field_hits.items():
        print(f"{k:>10} accuracy: {hit}/{tot} = {hit / tot:.0%}")
    p = total_tp / (total_tp + total_fp) if total_tp + total_fp else 1
    r = total_tp / (total_tp + total_fn) if total_tp + total_fn else 1
    f1 = 2 * p * r / (p + r) if p + r else 0
    print(f"{'skills':>10}: precision={p:.0%} recall={r:.0%} F1={f1:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
