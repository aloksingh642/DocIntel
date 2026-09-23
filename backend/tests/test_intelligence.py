"""Unit tests: normalization, duplicate detection, skill matching."""
from app.services.duplicate_service import (
    DuplicateService,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from app.services.normalization_service import NormalizationService
from app.services.skill_matching_service import SkillMatchingService


# ------------------------------ Normalization ------------------------------- #

def test_skill_normalization_with_seeded_aliases(db_session):
    svc = NormalizationService(db_session)
    assert svc.normalize_skill("Python programming") == "Python"
    assert svc.normalize_skill("Postgre SQL") == "PostgreSQL"
    assert svc.normalize_skill("amazon web services") == "AWS"
    assert svc.normalize_skill("React.js") == "React"
    assert svc.normalize_skill("Node JS") == "Node.js"
    assert svc.normalize_skill("postgres") == "PostgreSQL"


def test_normalize_many_dedupes(db_session):
    svc = NormalizationService(db_session)
    out = svc.normalize_many(["Python", "python programming", "postgres", "Postgre SQL"])
    assert out == ["Python", "PostgreSQL"]


def test_admin_alias_override(db_session):
    from app.models.profile import SkillAlias

    db_session.add(SkillAlias(alias="fast api", canonical="FastAPI"))
    db_session.commit()
    svc = NormalizationService(db_session)
    assert svc.normalize_skill("Fast API") == "FastAPI"


# --------------------------- Duplicate detection ---------------------------- #

def test_identity_normalizers():
    assert normalize_email(" John@Gmail.com ") == "john@gmail.com"
    assert normalize_phone("+91-98765 43210") == "9876543210"
    assert normalize_name("  JOHN   DOE ") == "john doe"


def test_content_similarity_flags_near_identical_text(db_session):
    from app.models.document import Document

    shared = (
        "Experienced backend developer with strong Python FastAPI PostgreSQL Docker "
        "Kubernetes AWS microservices REST distributed systems experience across "
        "payments platforms and large scale data pipelines"
    )
    db_session.add_all([
        Document(filename="a.txt", stored_filename="a", file_path="/tmp/a", file_type=".txt",
                 file_size=10, file_hash="h1", extracted_text=shared + " alpha"),
        Document(filename="b.txt", stored_filename="b", file_path="/tmp/b", file_type=".txt",
                 file_size=10, file_hash="h2", extracted_text=shared + " beta"),
    ])
    db_session.commit()

    svc = DuplicateService(db_session)
    report = svc.check_content_similarity(shared + " alpha gamma")
    assert report.is_duplicate
    assert report.duplicate_type == "content_similarity"
    assert report.similarity and report.similarity >= 0.8
    assert report.matched_document_id is not None


def test_content_similarity_ignores_unrelated_text(db_session):
    svc = DuplicateService(db_session)
    report = svc.check_content_similarity(
        "Delicious mediterranean recipes for olive oil cake and lemon tart."
    )
    assert not report.is_duplicate


# ----------------------------- Skill matching ------------------------------- #

def test_match_formula_is_transparent(db_session):
    svc = SkillMatchingService(db_session)
    comp = svc.compute(
        candidate_skills=["Python", "PostgreSQL", "Docker", "AWS"],
        required_skills=["Python", "FastAPI", "Postgre SQL", "Docker", "amazon web services"],
    )
    assert set(comp.matched_skills) == {"Python", "PostgreSQL", "Docker", "AWS"}
    assert comp.missing_skills == ["FastAPI"]
    # matched required / total required * 100 = 4/5 = 80
    assert comp.match_percentage == 80.0


def test_zero_required_skills_is_zero_percent(db_session):
    svc = SkillMatchingService(db_session)
    assert svc.compute(["Python"], []).match_percentage == 0.0
