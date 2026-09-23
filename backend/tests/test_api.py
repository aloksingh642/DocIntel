"""End-to-end API tests: auth, upload -> process flow, search, jobs, matching,
analytics, authorization. Background tasks run synchronously under TestClient."""
from tests.conftest import SAMPLE_RESUME

API = "/api/v1"


# ------------------------------- Auth --------------------------------------- #

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_login(client):
    resp = client.post(f"{API}/auth/register", json={
        "name": "Viewer One", "email": "viewer@example.com", "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "viewer"  # default role

    resp = client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_wrong_password_rejected(client):
    resp = client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "wrong-password",
    })
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "BAD_CREDENTIALS"


def test_login_sets_cookie_and_cookie_authenticates(client):
    """After login, a request WITHOUT the Authorization header still works —
    the HttpOnly cookie is an accepted channel (usable behind proxies that
    strip Authorization)."""
    client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })
    assert "access_token" in client.cookies
    resp = client.get(f"{API}/auth/me")  # no Authorization header on purpose
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "viewer@example.com"


def test_me_requires_token(client):
    # Clear the cookie jar explicitly: no header + no cookie must be a 401.
    client.cookies.clear()
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.get(f"{API}/documents").status_code == 401
    # restore a cookie for session-scoped client reuse safety
    client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })


# ------------------------------ Upload flow --------------------------------- #

def test_upload_process_and_retrieve(client, auth_headers, processed_resume_id):
    doc_id = processed_resume_id

    # detail
    resp = client.get(f"{API}/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 200
    doc = resp.json()["data"]
    assert doc["processing_status"] == "completed"
    assert doc["document_type"] == "resume"
    assert doc["classification_confidence"] >= 0.8

    # stage trace exists with timings
    resp = client.get(f"{API}/documents/{doc_id}/status", headers=auth_headers)
    logs = resp.json()["data"]["logs"]
    stages = {l["stage"] for l in logs}
    assert {"extract", "classify", "ai_extract", "duplicate_check", "persist"} <= stages
    assert all(l["processing_time"] is not None for l in logs if l["status"] != "info")

    # extraction payload
    resp = client.get(f"{API}/documents/{doc_id}/extraction", headers=auth_headers)
    data = resp.json()["data"]
    assert data["candidate"]["email"] == "john.doe@gmail.com"
    assert {"Python", "AWS", "Docker", "SQL", "Machine Learning"} <= set(data["skills"])
    assert data["total_experience_years"] == 1.5


def test_upload_rejects_bad_extension(client, auth_headers):
    resp = client.post(
        f"{API}/documents/upload",
        files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "FILE_VALIDATION_FAILED"


def test_exact_duplicate_reupload_returns_original(client, auth_headers, processed_resume_id):
    resp = client.post(
        f"{API}/documents/upload",
        files={"file": ("copy_of_resume.txt", SAMPLE_RESUME.encode(), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["exact_duplicate"] is True
    assert body["document"]["id"] == processed_resume_id


# ------------------------------ Authorization ------------------------------- #

def test_viewer_cannot_upload(client):
    login = client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(
        f"{API}/documents/upload",
        files={"file": ("r.txt", b"hello", "text/plain")},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # ...but read-only access works
    assert client.get(f"{API}/documents", headers=viewer_headers).status_code == 200


def test_delete_requires_admin(client, processed_resume_id, auth_headers):
    # create a viewer, try to delete (viewer lacks 'delete')
    login = client.post(f"{API}/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = client.delete(f"{API}/documents/{processed_resume_id}", headers=viewer_headers)
    assert resp.status_code == 403


# --------------------------- Candidates & search ---------------------------- #

def test_candidate_search(client, auth_headers):
    resp = client.get(f"{API}/candidates/search", headers=auth_headers,
                      params={"skill": "python"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert any(c["name"] == "John Doe" for c in items)

    resp = client.get(f"{API}/candidates/search", headers=auth_headers,
                      params={"q": "john.doe@gmail.com"})
    assert resp.json()["data"]["total"] >= 1


def test_candidate_profile(client, auth_headers):
    resp = client.get(f"{API}/candidates/search", headers=auth_headers, params={"skill": "python"})
    cand = resp.json()["data"]["items"][0]
    resp = client.get(f"{API}/candidates/{cand['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["email"] == "john.doe@gmail.com"
    assert len(data["documents"]) >= 1


# ------------------------------ Jobs & matching ----------------------------- #

def test_job_creation_and_matching(client, auth_headers):
    resp = client.post(f"{API}/jobs", headers=auth_headers, json={
        "title": "Python Backend Developer",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
    })
    assert resp.status_code == 201
    job_id = resp.json()["data"]["id"]

    resp = client.post(f"{API}/jobs/{job_id}/match", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()["data"]
    john = next(r for r in results if r["candidate_name"] == "John Doe")
    assert john["match_percentage"] == 60.0  # Python, Docker, AWS match (3/5)
    assert set(john["matched_skills"]) == {"Python", "Docker", "AWS"}
    assert set(john["missing_skills"]) == {"FastAPI", "PostgreSQL"}
    assert "matched" in john["formula"]


# ------------------------------- Analytics ---------------------------------- #

def test_analytics_endpoints(client, auth_headers):
    overview = client.get(f"{API}/analytics/overview", headers=auth_headers)
    assert overview.status_code == 200
    data = overview.json()["data"]
    assert data["total_documents"] >= 1
    assert data["processed_documents"] >= 1
    assert data["total_candidates"] >= 1

    skills = client.get(f"{API}/analytics/skills", headers=auth_headers)
    names = {s["skill"] for s in skills.json()["data"]}
    assert "Python" in names

    docs = client.get(f"{API}/analytics/documents", headers=auth_headers)
    assert any(t["type"] == "resume" for t in docs.json()["data"]["by_type"])


# ------------------------------ Error envelope ------------------------------ #

def test_consistent_error_envelope(client, auth_headers):
    resp = client.get(f"{API}/documents/999999", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == {"code": "NOT_FOUND", "message": "Document not found."}
