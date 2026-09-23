"""Tests for v2 real-life features: ATS workflow, CSV export, semantic search,
weighted matching, runtime settings, change password, webhooks."""
from tests.conftest import API, SAMPLE_RESUME


# ------------------------------ ATS workflow -------------------------------- #

def _john_id(client, headers):
    resp = client.get(f"{API}/candidates/search", headers=headers, params={"skill": "python"})
    return resp.json()["data"]["items"][0]["id"]


def test_status_transition_and_audit(client, auth_headers):
    cand_id = _john_id(client, auth_headers)
    resp = client.put(f"{API}/candidates/{cand_id}/status",
                      json={"status": "shortlisted"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "shortlisted"

    # invalid status rejected
    bad = client.put(f"{API}/candidates/{cand_id}/status",
                     json={"status": "maybe"}, headers=auth_headers)
    assert bad.status_code == 400

    # filter by status
    resp = client.get(f"{API}/candidates/search", headers=auth_headers,
                      params={"status": "shortlisted"})
    assert any(c["id"] == cand_id for c in resp.json()["data"]["items"])


def test_notes_and_tags(client, auth_headers):
    cand_id = _john_id(client, auth_headers)

    resp = client.post(f"{API}/candidates/{cand_id}/notes",
                       json={"text": "Strong backend fit, call Tuesday."}, headers=auth_headers)
    assert resp.status_code == 201

    resp = client.post(f"{API}/candidates/{cand_id}/tags",
                       json={"tag": "Urgent"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["tags"] == ["urgent"]  # normalized to lowercase

    # profile now exposes notes + tags
    profile = client.get(f"{API}/candidates/{cand_id}", headers=auth_headers).json()["data"]
    assert any("backend fit" in n["text"] for n in profile["notes"])
    assert profile["tags"] == ["urgent"]

    # filter by tag
    resp = client.get(f"{API}/candidates/search", headers=auth_headers, params={"tag": "urgent"})
    assert any(c["id"] == cand_id for c in resp.json()["data"]["items"])


# ------------------------------- CSV export --------------------------------- #

def test_csv_export(client, auth_headers):
    resp = client.get(f"{API}/candidates/export.csv", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert body.splitlines()[0].startswith("id,name,email")
    assert "john.doe@gmail.com" in body
    assert "John Doe" in body


def test_csv_export_respects_filters(client, auth_headers):
    resp = client.get(f"{API}/candidates/export.csv", headers=auth_headers,
                      params={"skill": "nonexistent-skill-xyz"})
    assert "john.doe@gmail.com" not in resp.text


# ----------------------------- Semantic search ------------------------------- #

def test_semantic_search_ranks_relevant_candidate(client, auth_headers):
    resp = client.get(f"{API}/candidates/semantic-search", headers=auth_headers,
                      params={"q": "python backend developer docker cloud"})
    assert resp.status_code == 200
    hits = resp.json()["data"]
    assert hits, "expected at least one semantic hit"
    assert hits[0]["score"] >= hits[-1]["score"]  # sorted desc
    # John Doe literally has Python, Docker, AWS on his resume
    names = [h["name"] for h in hits]
    assert "John Doe" in names


def test_semantic_search_empty_query_rejected(client, auth_headers):
    assert client.get(f"{API}/candidates/semantic-search?q=a",
                      headers=auth_headers).status_code == 422


# --------------------------- Weighted matching ------------------------------- #

def test_weighted_matching_with_nice_to_have(client, auth_headers):
    resp = client.post(f"{API}/jobs", headers=auth_headers, json={
        "title": "Cloud Python Engineer",
        "required_skills": ["Python", "AWS"],
        "nice_to_have_skills": ["Machine Learning", "Kubernetes"],
    })
    assert resp.status_code == 201, resp.text
    job = resp.json()["data"]
    assert job["nice_to_have_skills"] == ["Machine Learning", "Kubernetes"]

    resp = client.post(f"{API}/jobs/{job['id']}/match", headers=auth_headers)
    results = resp.json()["data"]
    john = next(r for r in results if r["candidate_name"] == "John Doe")
    # required: Python+AWS both matched (2/2 = 1.0)
    # nice: Machine Learning matched (1/2 = 0.5)
    # score = 0.7*1.0 + 0.3*0.5 = 0.85 -> 85.0
    assert john["match_percentage"] == 85.0
    assert "w_req=0.7" in john["formula"]
    assert john["matched_nice"] == ["Machine Learning"]
    assert john["missing_nice"] == ["Kubernetes"]


def test_weight_change_affects_score(client, auth_headers, db_session):
    from app.models.matching import Job
    from app.models.profile import Candidate
    from app.services.settings_service import SettingsService
    from app.services.skill_matching_service import SkillMatchingService

    SettingsService(db_session).set("skill_match_required_weight", 0.5, None)
    db_session.expire_all()
    job = db_session.query(Job).filter(Job.title == "Cloud Python Engineer").first()
    john = db_session.query(Candidate).filter(Candidate.name == "John Doe").first()
    comp = SkillMatchingService(db_session).compute(
        [cs.skill.name for cs in john.skills], job.required_skills, job.nice_to_have_skills
    )
    # w_req=0.5: 0.5*1.0 + 0.5*0.5 = 0.75
    assert comp.match_percentage == 75.0
    # restore default for other tests
    SettingsService(db_session).set("skill_match_required_weight", 0.7, None)


# ---------------------------- Runtime settings ------------------------------- #

def test_settings_flow(client, auth_headers):
    resp = client.get(f"{API}/admin/settings", headers=auth_headers)
    assert resp.status_code == 200
    keys = {s["key"] for s in resp.json()["data"]}
    assert "classification_confidence_threshold" in keys

    resp = client.put(f"{API}/admin/settings", headers=auth_headers,
                      json={"values": {"classification_confidence_threshold": 0.5}})
    assert resp.status_code == 200
    assert resp.json()["data"]["classification_confidence_threshold"] == 0.5

    # out-of-range rejected
    bad = client.put(f"{API}/admin/settings", headers=auth_headers,
                     json={"values": {"duplicate_similarity_threshold": 5.0}})
    assert bad.status_code == 422

    # unknown key rejected
    unknown = client.put(f"{API}/admin/settings", headers=auth_headers,
                         json={"values": {"nonsense": 0.5}})
    assert unknown.status_code == 400

    # restore
    client.put(f"{API}/admin/settings", headers=auth_headers,
               json={"values": {"classification_confidence_threshold": 0.8}})


# ----------------------------- Change password ------------------------------- #

def test_change_password(client, auth_headers):
    # register a temp user
    client.post(f"{API}/auth/register", json={
        "name": "Temp", "email": "temp@example.com", "password": "temppassword",
    })
    login = client.post(f"{API}/auth/login", json={
        "email": "temp@example.com", "password": "temppassword",
    }).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    wrong = client.post(f"{API}/auth/change-password", headers=headers,
                        json={"current_password": "nope-nope", "new_password": "newpassword1"})
    assert wrong.status_code == 400

    ok = client.post(f"{API}/auth/change-password", headers=headers,
                     json={"current_password": "temppassword", "new_password": "newpassword1"})
    assert ok.status_code == 200

    # old no longer works, new works
    assert client.post(f"{API}/auth/login", json={
        "email": "temp@example.com", "password": "temppassword"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={
        "email": "temp@example.com", "password": "newpassword1"}).status_code == 200


# ------------------------------- Webhooks ------------------------------------ #

def test_webhook_crud_and_delivery_record(client, auth_headers):
    resp = client.post(f"{API}/admin/webhooks", headers=auth_headers,
                       json={"url": "http://127.0.0.1:9/unreachable", "secret": "s3cret"})
    assert resp.status_code == 201
    hook_id = resp.json()["data"]["id"]

    # processing a document fires the webhook; delivery failure is recorded, not raised
    up = client.post(f"{API}/documents/upload", headers=auth_headers,
                     files={"file": ("webhook_probe.txt",
                                     (SAMPLE_RESUME + "\nwebhook probe variant\n").encode(),
                                     "text/plain")})
    assert up.status_code == 201

    deliveries = client.get(f"{API}/admin/webhook-deliveries", headers=auth_headers).json()["data"]
    assert any(d["webhook_id"] == hook_id and d["success"] is False and d["error"]
               for d in deliveries)

    # toggle and delete
    toggled = client.put(f"{API}/admin/webhooks/{hook_id}/toggle", headers=auth_headers)
    assert toggled.json()["data"]["active"] is False
    assert client.delete(f"{API}/admin/webhooks/{hook_id}", headers=auth_headers).status_code == 200


def test_webhook_rejects_bad_url(client, auth_headers):
    bad = client.post(f"{API}/admin/webhooks", headers=auth_headers,
                      json={"url": "ftp://not-a-webhook"})
    assert bad.status_code == 422
