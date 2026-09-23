"""Seed a deployed (or local) IDP instance with the sample dataset and demo jobs.

Usage:
    python scripts/demo_seed.py --base-url https://idp-system.onrender.com

Credentials default to ADMIN_EMAIL / IDP_ADMIN_PASSWORD env vars; you will be
prompted for the password if it is not provided.

The script uploads every file in sample_dataset/ (including the corrupted and
duplicate samples — those intentionally end up failed / needs_review so the
review queue has something to show), waits for background processing to drain,
creates two demo jobs, runs matching, and prints a summary.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

import httpx

API = "/api/v1"
DATASET = Path(__file__).resolve().parents[2] / "sample_dataset"

MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}
PENDING = {"pending", "queued", "processing"}

JOBS = [
    {
        "title": "Python Backend Developer",
        "description": "Build and maintain REST APIs, services and data pipelines.",
        "required_skills": ["Python", "Django", "FastAPI", "PostgreSQL"],
        "nice_to_have_skills": ["Docker", "AWS"],
    },
    {
        "title": "Cloud Platform Engineer",
        "description": "Design and operate scalable cloud infrastructure for ML workloads.",
        "required_skills": ["AWS", "Docker", "Terraform"],
        "nice_to_have_skills": ["Kubernetes", "Machine Learning"],
    },
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=os.getenv("IDP_BASE_URL", "http://localhost:8000"))
    p.add_argument("--email", default=os.getenv("IDP_ADMIN_EMAIL", "admin@idp.dev"))
    p.add_argument("--password", default=os.getenv("IDP_ADMIN_PASSWORD", ""))
    p.add_argument("--timeout", type=int, default=180, help="Seconds to wait for processing.")
    args = p.parse_args()
    password = args.password or getpass.getpass(f"Password for {args.email}: ")

    base = args.base_url.rstrip("/")
    client = httpx.Client(base_url=base, timeout=60.0)

    # ---- login -------------------------------------------------------------
    r = client.post(f"{API}/auth/login", json={"email": args.email, "password": password})
    if r.status_code != 200:
        print(f"✗ Login failed ({r.status_code}): {r.text[:200]}", file=sys.stderr)
        return 1
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    print(f"✓ Logged in to {base} as {args.email}")

    # ---- upload the sample dataset -----------------------------------------
    files = sorted(
        f for f in DATASET.iterdir()
        if f.is_file() and f.suffix.lower() in MIME
    )
    print(f"↑ Uploading {len(files)} sample documents from {DATASET.name}/ ...")
    uploaded = 0
    for path in files:
        r = client.post(
            f"{API}/documents/upload",
            files={"file": (path.name, path.read_bytes(), MIME[path.suffix.lower()])},
        )
        if r.status_code in (200, 201, 202):
            uploaded += 1
            print(f"  ✓ {path.name}")
        else:
            print(f"  ✗ {path.name}: HTTP {r.status_code} {r.text[:120]}")
    print(f"✓ Accepted {uploaded}/{len(files)} uploads")

    # ---- wait for the pipeline to drain ------------------------------------
    print("⏳ Waiting for background processing ...")
    deadline = time.time() + args.timeout
    items = []
    while time.time() < deadline:
        r = client.get(f"{API}/documents", params={"page_size": 100})
        items = (r.json().get("data") or {}).get("items", [])
        if items and not any(d.get("processing_status") in PENDING for d in items):
            break
        time.sleep(3)

    counts: dict[str, int] = {}
    for d in items:
        counts[d.get("processing_status", "?")] = counts.get(d.get("processing_status", "?"), 0) + 1
    print("✓ Documents:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")

    # ---- demo jobs + matching ----------------------------------------------
    titles = {j["title"] for j in JOBS}
    existing = {j["title"]: j["id"] for j in (client.get(f"{API}/jobs").json().get("data") or [])}
    for job in JOBS:
        if job["title"] in existing:
            print(f"  • Job already exists, skipping: {job['title']}")
            continue
        r = client.post(f"{API}/jobs", json=job)
        if r.status_code == 201:
            print(f"  ✓ Job created: {job['title']}")
        else:
            print(f"  ✗ Job '{job['title']}': HTTP {r.status_code} {r.text[:120]}")

    jobs = [j for j in (client.get(f"{API}/jobs").json().get("data") or []) if j["title"] in titles]
    for job in jobs:
        r = client.post(f"{API}/jobs/{job['id']}/match")
        if r.status_code != 200:
            print(f"  ✗ Matching failed for {job['title']}: HTTP {r.status_code}")
            continue
        top = (r.json().get("data") or [])[:3]
        print(f"  🎯 {job['title']} — top matches: " + (
            ", ".join(f"{m.get('candidate_name') or '?'} {m.get('match_percentage', 0):.1f}%" for m in top)
            or "no candidates yet"
        ))

    r = client.get(f"{API}/candidates", params={"page_size": 100})
    cands = r.json().get("data") or []
    if isinstance(cands, dict):
        cands = cands.get("items", [])
    print(f"\n✅ Seed complete: {len(cands)} candidates, {sum(counts.values())} documents, {len(jobs)} demo jobs.")
    print(f"   Open {base} and log in as {args.email} — try the Review queue and Job match pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
