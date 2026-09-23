"""AI layer tests: mock-provider extraction quality + strict schema validation.

No external AI API is used anywhere in the suite.
"""
import copy

import pytest
from pydantic import ValidationError

from app.ai.factory import get_llm_provider
from app.schemas.extraction import DocumentClassification, ExtractionResult
from app.services.extraction_service import ExtractionService

RESUME = """Jane Smith
jane.smith@example.com
+91-9123456780
Bengaluru, India

Professional Summary:
Backend engineer focused on APIs and data platforms.

Skills:
Python, FastAPI, PostgreSQL, Docker, React.js, amazon web services

Experience:
Senior Developer at Acme Corp (2021-2024)
3 years

Education:
M.Tech Computer Science, IIT Delhi, 2020

Certifications:
AWS Certified Solutions Architect

Languages:
English, Hindi
"""

SPARSE_RESUME = """Rahul Kumar

Skills:
Java, Spring Boot
"""


@pytest.fixture(scope="module")
def provider():
    return get_llm_provider("mock")


def test_full_extraction(provider):
    result = provider.extract_resume(RESUME)
    assert result.candidate.name == "Jane Smith"
    assert result.candidate.email == "jane.smith@example.com"
    assert result.candidate.phone == "+91-9123456780"
    assert result.candidate.location is not None and "Bengaluru" in result.candidate.location
    assert result.candidate.professional_summary is not None
    skills = set(result.skills)
    assert {"Python", "FastAPI", "PostgreSQL", "Docker", "React", "AWS"} <= skills
    assert result.total_experience_years == 3.0
    assert any(e.degree == "M.Tech" and e.field == "Computer Science" for e in result.education)
    assert any("AWS Certified" in c.name for c in result.certifications)
    assert any(l.language == "Hindi" for l in result.languages)
    assert result.field_sources.get("email") == "contact header"


def test_never_hallucinates_missing_fields(provider):
    """Sparse resume: unavailable scalars are None, lists are []."""
    result = provider.extract_resume(SPARSE_RESUME)
    assert result.candidate.email is None
    assert result.candidate.phone is None
    assert result.candidate.location is None
    assert result.total_experience_years is None
    assert result.experiences == []
    assert set(result.skills) == {"Java", "Spring Boot"}
    # everything validates through the pydantic schema
    ExtractionResult.model_validate(result.model_dump())


def test_extraction_service_validates(monkeypatch):
    class BadProvider:
        def extract_resume(self, text):
            raise ValidationError.from_exception_data(
                "ExtractionResult",
                [{"type": "missing", "loc": ("candidate",), "input": {}}],
            )

    from app.ai import factory

    monkeypatch.setattr(factory, "_PROVIDER_CACHE", {"mock": BadProvider()})
    from app.services.extraction_service import ExtractionValidationError

    with pytest.raises(ExtractionValidationError):
        ExtractionService().extract_resume("anything")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(confidence=1.5),               # confidence out of range
        lambda d: d.update(skills="Python"),              # wrong type for list
        lambda d: d.update(candidate={"name": 123}),      # wrong field type
    ],
)
def test_schema_rejects_malformed_ai_output(mutation):
    valid = ExtractionResult(skills=["Python"]).model_dump()
    broken = copy.deepcopy(valid)
    with pytest.raises((ValidationError, TypeError)):
        mutation(broken)
        ExtractionResult.model_validate(broken)


def test_classification_schema_bounds():
    with pytest.raises(ValidationError):
        DocumentClassification(document_type="resume", confidence=1.2)
    with pytest.raises(ValidationError):
        DocumentClassification(document_type="memo", confidence=0.5)  # unknown type
