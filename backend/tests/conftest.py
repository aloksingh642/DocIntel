"""Shared fixtures: isolated temp DB + temp upload dir + authenticated client.

Environment is configured BEFORE any app module import so the cached
Settings object picks up the test database.
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="idp_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TMP}/uploads"
os.environ["SECRET_KEY"] = "test-secret-key-for-idp-tests-minimum-32b"
os.environ["AI_PROVIDER"] = "mock"
os.environ["ADMIN_EMAIL"] = "admin@example.dev"
os.environ["ADMIN_PASSWORD"] = "admin1234"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


SAMPLE_RESUME = """John Doe
john.doe@gmail.com
+91-9876543210
Varanasi, India

Skills:
Python, SQL, AWS, Docker, Machine Learning

Experience:
1.5 years

Education:
B.Tech Computer Science
"""

SAMPLE_INVOICE = """INVOICE
Invoice Number: INV-2026-001
Bill To: Acme Corporation
Subtotal: 1000.00
Tax: 180.00
Total Due: 1180.00
Payment Terms: Net 30
Amount Due: 1180.00
"""

SAMPLE_CONTRACT = """SERVICES AGREEMENT
This agreement is entered into between the parties.
WHEREAS, the first party wishes to procure services;
Terms and Conditions apply. Governing law: India.
The parties agree to indemnify each other against claims.
"""


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """Direct DB session for service-level unit tests (same test database)."""
    from app.database.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    # default admin seeded at startup
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.dev", "password": "admin1234"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def processed_resume_id(client: TestClient, auth_headers: dict) -> int:
    """Upload + (synchronously, via TestClient) process a sample resume."""
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("john_doe_resume.txt", SAMPLE_RESUME.encode(), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()["data"]["document"]
    return doc["id"]
