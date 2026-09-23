"""Classification tests: every supported document class + threshold routing."""
import pytest

from app.services.classification_service import ClassificationService


@pytest.mark.parametrize(
    "text,expected",
    [
        ("John Doe\njohn@x.com\nSkills: Python\nExperience: 3 years\nEducation: B.Tech", "resume"),
        ("INVOICE\nInvoice Number: 5\nBill To: Acme\nAmount Due: 100\nSubtotal: 90\nTax: 10\nPayment Terms: Net 30", "invoice"),
        ("PURCHASE ORDER\nPO Number: 99\nShip To: Warehouse 4\nVendor: SupplyCo\nQuantity: 12\nUnit Price: 5.00\nDelivery Date: 2026-10-01", "purchase_order"),
        ("SERVICES AGREEMENT\nWHEREAS the parties agree...\nTerms and Conditions.\nGoverning Law: India.\nThe party shall indemnify the other party.", "contract"),
        ("CERTIFICATE OF COMPLETION\nThis is to certify that Jane Smith has completed the course.\nAwarded to Jane Smith. Issued on 2026-01-01.", "certificate"),
        ("a short note with no signals", "other"),
    ],
)
def test_classification_of_known_types(text, expected):
    svc = ClassificationService()
    result = svc.classify(text)
    assert result.document_type == expected


def test_resume_needs_contact_signals_for_high_confidence():
    svc = ClassificationService()
    result = svc.classify("skills\nexperience\neducation\nprojects")
    assert result.document_type == "resume"
    assert svc.needs_review(result.confidence)  # low confidence -> review queue


def test_threshold_boundary():
    svc = ClassificationService()
    assert svc.needs_review(0.79)
    assert not svc.needs_review(0.80)
    assert svc.needs_review(None)
