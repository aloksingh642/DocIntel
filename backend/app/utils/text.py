"""Text cleaning and common regex helpers (shared, no duplication of logic)."""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[-\s]?)?(?:\(?\d{3,5}\)?[-\s]?)?\d{3,5}[-\s]?\d{4,6}"
)
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[^\s]+", re.IGNORECASE)
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s)]+", re.IGNORECASE)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s)]+", re.IGNORECASE)
YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+(?:professional\s+)?experience)?",
    re.IGNORECASE,
)

_SECTION_HINTS = {
    "skills": re.compile(r"^\s*(technical\s+)?skills?\b[:\-]?", re.IGNORECASE),
    "experience": re.compile(r"^\s*(work\s+|professional\s+|employment\s+)?experience\b[:\-]?", re.IGNORECASE),
    "education": re.compile(r"^\s*education\b[:\-]?", re.IGNORECASE),
    "summary": re.compile(r"^\s*(professional\s+)?summary\b[:\-]?", re.IGNORECASE),
}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def section_of(line: str) -> str | None:
    for name, rx in _SECTION_HINTS.items():
        if rx.match(line.strip()):
            return name
    return None
