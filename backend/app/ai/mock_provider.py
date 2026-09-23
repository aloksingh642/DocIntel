"""Deterministic, offline extraction/classification provider.

Implements genuine NLP heuristics (regexes, section parsing, dictionary
matching against the canonical skill taxonomy) so the full pipeline runs
reproducibly with no external API — the default for local development and
for the automated test-suite. It is a drop-in replacement for an LLM:
same interface, same Pydantic-validated output.
"""
from __future__ import annotations

import re

from app.ai.base import LLMProvider
from app.schemas.extraction import (
    CandidateInfo,
    CertificationItem,
    DocumentClassification,
    EducationItem,
    ExperienceItem,
    ExtractionResult,
    LanguageItem,
    ProjectItem,
)
from app.services.skill_data import DEFAULT_SKILL_ALIASES, SKILL_TAXONOMY
from app.utils.text import (
    EMAIL_RE,
    GITHUB_RE,
    LINKEDIN_RE,
    PHONE_RE,
    URL_RE,
    YEARS_RE,
    section_of,
)

_DEGREES = [
    "Ph.D", "PhD", "MBA", "M.Tech", "M.Tech.", "MTech", "M.Sc", "MSc", "M.S.",
    "MCA", "B.Tech", "BTech", "B.E.", "B.Tech.", "Bachelor of Technology",
    "Bachelor of Engineering", "B.Sc", "BSc", "B.S.", "BCA", "BBA", "Bachelor",
    "Master of Technology", "Master of Science", "Master",
]
_FIELDS = [
    "Computer Science", "Information Technology", "Electronics", "Electrical",
    "Mechanical", "Civil", "Data Science", "Artificial Intelligence",
    "Mathematics", "Physics", "Software Engineering", "Business Administration",
    "Commerce", "Economics", "Statistics",
]
_CERT_HINTS = re.compile(
    r"(certified|certification|certificate)\b", re.IGNORECASE
)
_KNOWN_LANGUAGES = [
    "English", "Hindi", "Spanish", "French", "German", "Mandarin", "Japanese",
    "Tamil", "Telugu", "Bengali", "Marathi", "Kannada", "Urdu", "Arabic",
]
_COUNTRY_PTRNS = re.compile(
    r"\b(India|USA|United States|UK|United Kingdom|Canada|Australia|Germany|"
    r"Singapore|UAE|Netherlands|France|Japan)\b"
)
_CITY_PTRNS = re.compile(
    r"\b(Varanasi|Mumbai|Delhi|New Delhi|Bengaluru|Bangalore|Hyderabad|Chennai|"
    r"Pune|Kolkata|Noida|Gurugram|Jaipur|Lucknow|Ahmedabad|San Francisco|"
    r"New York|London|Berlin|Toronto|Sydney|Singapore)\b",
    re.IGNORECASE,
)
_NAME_REJECT = re.compile(
    r"resume|curriculum|vitae|email|phone|address|skills|experience|education|"
    r"summary|objective|@|http|\d{3,}|linkedin|github",
    re.IGNORECASE,
)


def _match_skills(text: str) -> list[str]:
    """Dictionary extraction over text — only reports skills that literally occur."""
    found: dict[str, None] = {}
    lowered = text.lower()
    # longest-first so "amazon web services" wins before "aws" substrings
    vocab = sorted(
        {**{k.lower(): k for k in SKILL_TAXONOMY}, **DEFAULT_SKILL_ALIASES},
        key=len,
        reverse=True,
    )
    for variant in vocab:
        canonical = {**{k.lower(): k for k in SKILL_TAXONOMY}, **DEFAULT_SKILL_ALIASES}[variant]
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(variant)}(?![A-Za-z0-9+#])"
        if re.search(pattern, lowered):
            found[canonical] = None
    return list(found)


def _looks_like_name(line: str) -> bool:
    words = line.strip().split()
    if not (2 <= len(words) <= 4) or _NAME_REJECT.search(line):
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", w) for w in words)


class MockLLMProvider(LLMProvider):
    """Heuristic provider — deterministic, fully offline, honest about uncertainty."""

    name = "mock"

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    _CLASS_KEYWORDS: dict[str, list[str]] = {
        "invoice": ["invoice", "bill to", "invoice number", "amount due",
                    "subtotal", "total due", "payment terms", "tax"],
        "purchase_order": ["purchase order", "po number", "po no", "ship to",
                           "quantity", "unit price", "vendor", "delivery date"],
        "contract": ["agreement", "hereby", "party", "parties", "terms and conditions",
                     "governing law", "whereas", "indemnify", "termination clause"],
        "certificate": ["certificate", "certify that", "awarded to", "has completed",
                        "issued on", "this is to certify", "of completion"],
        "resume": ["resume", "curriculum vitae", "skills", "experience",
                   "education", "objective", "summary", "employment", "projects"],
    }

    def classify_document(self, text: str) -> DocumentClassification:
        lowered = text.lower()
        scores = {
            doc_type: sum(2 if kw in ("resume", "invoice number", "purchase order")
                          else 1 for kw in kws if kw in lowered)
            for doc_type, kws in self._CLASS_KEYWORDS.items()
        }
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        if scores[best] == 0 or total == 0:
            return DocumentClassification(document_type="other", confidence=0.35)
        confidence = min(0.99, 0.55 + (scores[best] / (total + 4)))
        # Resume must show genuine contact signals to earn high confidence.
        if best == "resume" and not (EMAIL_RE.search(text) or PHONE_RE.search(text)):
            confidence = min(confidence, 0.72)
        return DocumentClassification(document_type=best, confidence=round(confidence, 3))

    # ------------------------------------------------------------------ #
    # Resume extraction
    # ------------------------------------------------------------------ #
    def extract_resume(self, text: str) -> ExtractionResult:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        sources: dict[str, str] = {}

        # --- contact signals -------------------------------------------------
        email = (EMAIL_RE.search(text) or [None])[0] if EMAIL_RE.search(text) else None
        email_m = EMAIL_RE.search(text)
        email = email_m.group(0) if email_m else None
        if email:
            sources["email"] = "contact header"
        phone_m = PHONE_RE.search(text)
        phone = phone_m.group(0).strip() if phone_m else None
        if phone and phone_m:
            sources["phone"] = "contact header"
        li = LINKEDIN_RE.search(text)
        gh = GITHUB_RE.search(text)
        # Portfolio: any URL that is not a profile link and not an email address.
        portfolio_urls = [
            u.group(0) for u in URL_RE.finditer(text)
            if "@" not in u.group(0)
            and "linkedin" not in u.group(0).lower()
            and "github" not in u.group(0).lower()
            and re.search(r"(https?://|\.(dev|me|io|com|org|net)\b)", u.group(0))
        ]

        # --- name -------------------------------------------------------------
        name = None
        for ln in lines[:6]:  # header zone only — avoids grabbing job titles
            cleaned = re.sub(r"^(name)[:\-]\s*", "", ln, flags=re.IGNORECASE).strip()
            if _looks_like_name(cleaned) and (not email or email not in ln):
                name = cleaned.title() if cleaned.isupper() else cleaned
                sources["name"] = "document header"
                break

        # --- location ---------------------------------------------------------
        location = None
        for ln in lines[:12]:
            if re.match(r"^location\b[:\-]?", ln, re.IGNORECASE):
                location = re.sub(r"^location\b[:\-]?\s*", "", ln, flags=re.IGNORECASE) or None
            elif _COUNTRY_PTRNS.search(ln) or _CITY_PTRNS.search(ln):
                city = _CITY_PTRNS.search(ln)
                country = _COUNTRY_PTRNS.search(ln)
                if city and country:
                    location = _title_c(city.group(0)) + ", " + country.group(0)
                elif (city or country) and len(ln) < 60 and not EMAIL_RE.search(ln):
                    location = _title_c((city or country).group(0))
            if location:
                if _NAME_REJECT.search(location) and not _CITY_PTRNS.search(location):
                    location = None
                    continue
                sources["location"] = "contact header"
                break

        # --- sections ---------------------------------------------------------
        sections: dict[str, list[str]] = {}
        current = "header"
        for ln in lines:
            sec = section_of(ln)
            if sec:
                current = sec
                continue
            sections.setdefault(current, []).append(ln)

        skills = _match_skills(text)
        if skills:
            sources["skills"] = "skills section" if "skills" in sections else "full text scan"

        years = None
        for m in YEARS_RE.finditer(text):
            val = float(m.group(1))
            if 0 < val <= 50:
                years = val if years is None else max(years, val)
        if years is not None:
            sources["total_experience_years"] = "experience statement"

        # --- education --------------------------------------------------------
        education: list[EducationItem] = []
        for ln in sections.get("education", []) + [l for l in lines if "university" in l.lower() or "college" in l.lower()]:
            deg = next((d for d in _DEGREES if d.lower() in ln.lower()), None)
            year_m = re.search(r"\b(19|20)\d{2}\b", ln)
            if deg or _FIELDS_HIT(ln):
                education.append(EducationItem(
                    degree=deg,
                    field=next((f for f in _FIELDS if f.lower() in ln.lower()), None),
                    institution=_institution_guess(ln),
                    end_year=int(year_m.group(0)) if year_m else None,
                ))
        if education:
            sources["education"] = "education section"

        # --- certifications ---------------------------------------------------
        certifications: list[CertificationItem] = []
        cert_lines = sections.get("certifications", []) + [
            l for l in lines if _CERT_HINTS.search(l) and "certif" in l.lower()
        ]
        seen = set()
        for ln in cert_lines:
            cleaned = ln.lstrip("-•* ").strip()
            if cleaned and len(cleaned) > 4 and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                issuer = None
                for org in ("AWS", "Microsoft", "Google", "Oracle", "Cisco", "Coursera", "Udemy"):
                    if org.lower() in cleaned.lower():
                        issuer = org
                        break
                certifications.append(CertificationItem(name=cleaned[:160], issuer=issuer))
        certifications = certifications[:5]

        # --- experiences --------------------------------------------------------
        experiences: list[ExperienceItem] = []
        for ln in sections.get("experience", []):
            if re.search(r"\b(19|20)\d{2}\b", ln) or " at " in ln.lower():
                experiences.append(
                    ExperienceItem(description=ln[:300])
                )
        experiences = experiences[:8]

        # --- projects ---------------------------------------------------------
        projects: list[ProjectItem] = []
        for ln in sections.get("projects", []):
            m = re.match(r"^[-•*]?\s*([A-Z][\w .\-]{2,60}?)[:\-–]\s*(.+)$", ln)
            if m and len(projects) < 6:
                projects.append(ProjectItem(name=m.group(1).strip(), description=m.group(2).strip()[:400]))
        if not projects:
            for ln in sections.get("projects", [])[:6]:
                cleaned = ln.lstrip("-•* ").strip()
                if cleaned:
                    projects.append(ProjectItem(name=cleaned[:80], description=None))

        # --- languages --------------------------------------------------------
        languages = [
            LanguageItem(language=lang)
            for lang in _KNOWN_LANGUAGES
            if re.search(rf"(?<![A-Za-z]){lang}(?![A-Za-z])", text, re.IGNORECASE)
               and ("language" in text.lower())
        ]

        # --- summary ----------------------------------------------------------
        summary_lines = sections.get("summary", [])[:4]
        summary = " ".join(summary_lines) if summary_lines else None
        if summary:
            sources["professional_summary"] = "summary section"

        confidence = round(min(0.97, 0.6 + 0.05 * sum(bool(x) for x in (
            name, email, phone, skills, education))), 3)

        return ExtractionResult(
            candidate=CandidateInfo(
                name=name, email=email, phone=phone, location=location,
                linkedin=li.group(0) if li else None,
                github=gh.group(0) if gh else None,
                portfolio=portfolio_urls[0] if portfolio_urls else None,
                professional_summary=summary,
            ),
            skills=skills,
            experiences=experiences,
            education=education,
            certifications=certifications,
            projects=projects,
            languages=languages,
            total_experience_years=years,
            field_sources=sources,
            confidence=confidence,
        )


def _FIELDS_HIT(line: str) -> str | None:
    return next((f for f in _FIELDS if f.lower() in line.lower()), None)


def _institution_guess(line: str) -> str | None:
    m = re.search(
        r"([A-Z][\w&.' -]*\b(?:University|College|Institute|IIT|NIT|IIIT|School)\b[\w&.' -]*)",
        line,
    )
    return m.group(1).strip(" ,.-") if m else None


def _title_c(value: str) -> str:
    return " ".join(w.capitalize() for w in value.split())
