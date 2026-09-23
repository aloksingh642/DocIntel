# Intelligent Document Processing (IDP) System

An AI-powered document processing platform that accepts business documents,
extracts text (with OCR when needed), classifies the document, extracts
structured information through a validated AI layer, normalizes it, detects
duplicates, matches candidate skills against job requirements, stores
everything in a relational database, and visualizes the results in a modern
web dashboard.

The primary use case today is **resume / candidate document processing**, with
an architecture designed to add invoices, contracts, purchase orders,
certificates and other document categories later.

> **Safety contract:** the system only extracts what is explicitly present in a
> document. Missing scalars are `null`, missing lists are `[]`. Never
> hallucinated, never inferred-as-fact. All AI output is schema-validated
> before it touches the database, low-confidence results are routed to human
> review, and every edit is audited.

---

## Table of contents

1. [Architecture](#architecture)
2. [Features](#features)
3. [Technology stack](#technology-stack)
4. [Quick start (local)](#quick-start-local-without-docker)
5. [Environment variables](#environment-variables)
6. [Database setup & migrations](#database-setup--migrations)
7. [Running the application](#running-the-application)
8. [API documentation](#api-documentation)
9. [AI configuration](#ai-configuration)
10. [Testing](#testing)
11. [Evaluation dataset](#evaluation-dataset)
12. [Docker](#docker)
13. [Deploy to Render](#deploy-to-render-free)
14. [Security model](#security-model)
15. [Human review & audit](#human-review--audit)
16. [Troubleshooting](#troubleshooting)
17. [Project structure](#project-structure)

---

## Architecture

```
                        ┌─────────────────────────────┐
                        │  React SPA (dashboard)      │
                        └──────────────┬──────────────┘
                                       │ REST /api/v1  (JWT)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                              FastAPI application                            │
│                                                                             │
│  api/            services/                 ai/                extractors/   │
│  ─ auth          ─ document_service        ─ LLMProvider ABC  ─ pdf         │
│  ─ documents     ─ pipeline (orchestrator)   ├ MockLLM        ─ docx        │
│  ─ candidates    ─ classification_service    └ OpenAI         ─ txt         │
│  ─ skills/jobs   ─ extraction_service      ─ factory          ─ image       │
│  ─ analytics     ─ duplicate_service       ─ prompts          ─ ocr         │
│  ─ admin         ─ skill_matching_service  (pluggable)                      │
│                  ─ normalization_service                                    │
│                  ─ analytics_service                                        │
└──────┬───────────────┬──────────────────────────────┬───────────────────────┘
       │ SQLAlchemy    │ in-process workers           │ file store
       ▼               ▼ (Celery-compatible seam)    ▼
┌──────────────┐  ┌───────────────┐          ┌──────────────┐
│ PostgreSQL / │  │ Background    │          │ uploads/     │
│ SQLite (dev) │  │ task queue    │          │ (not web-    │
└──────────────┘  └───────────────┘          │  accessible) │
                                             └──────────────┘
```

### Processing pipeline

Each stage is independently timed, logged per-document, and failure-isolated.

```
upload → validate → extract (OCR fallback) → classify → AI extract
→ normalize → duplicate check (3 levels) → persist → complete / needs_review / failed
```

## Features

| Area | What you get |
|---|---|
| Upload | Drag & drop multi-file UI; extension + MIME + size validation; SHA-256 hashing; generated storage names; path-traversal protection |
| Extraction | PDF (direct text + OCR fallback for scans), DOCX (paragraphs + tables), TXT (encoding fallback), JPG/PNG through OCR preprocessing (grayscale → upscale → denoise → autocontrast) |
| Classification | Rule-based classifier today (resume / invoice / contract / purchase_order / certificate / other) with a confidence threshold that routes low-confidence files to `needs_review`; replaceable via the provider interface |
| AI extraction | Pluggable `LLMProvider` (offline deterministic provider by default, OpenAI provider included); strict Pydantic validation with safe-parse + retry; per-field source attribution |
| Normalization | Admin-editable skill alias dictionary (`postgres → PostgreSQL`, `React.js → React`, …) live in the DB — no deploys |
| Duplicates | Level 1 SHA-256 exact, Level 2 normalized identity (email/phone/name), Level 3 TF-IDF cosine similarity above a configurable threshold — flagged, never auto-deleted |
| Skill matching | Transparent formula `matched required / total required × 100`, stored per job/candidate with matched & missing lists |
| Search | Candidates by name/email/company/title, skill, location, degree, min experience, with pagination |
| Dashboard | Headline metrics, documents-by-type pie, processing-status bars, top-skills chart, uploads-over-time area chart |
| Analytics | Experience / education / location distributions, date-range filtering |
| Auth | JWT + bcrypt (cookie + header transports), roles `admin` / `recruiter` / `viewer` with a configurable permission map, self-service password change |
| Review | Approve/reject workflow on `needs_review` (dedicated **Review queue** page), candidate edit UI with audit trail of old→new values |
| Ops | Structured per-stage processing logs with durations, audit log, health endpoint, retry failed docs |

### Real-life workflow features (v2)

| Area | What you get |
|---|---|
| **Recruiting pipeline (mini-ATS)** | Candidate statuses `new → reviewing → shortlisted → interviewed → offer → hired / rejected`, recruiter **notes** with author & timestamp, **tags**; every transition audited; filter & CSV-export by status/tag |
| **CSV export** | `/candidates/export.csv` honours all search filters — spreadsheet-ready UTF-8 output |
| **Semantic search** | `/candidates/semantic-search?q=…` ranks profiles by TF-IDF cosine similarity between the query and each full candidate profile — "python backend developer with docker", not just keyword filters |
| **Weighted matching** | Jobs support a **nice-to-have** tier: `score = w_req·(matched req/total req) + w_nice·(matched nice/total nice)·100` (default 0.7/0.3) |
| **Runtime thresholds** | Admin-editable, DB-backed tuning of classification & duplicate thresholds and match weights from the UI — no redeploy (`app_settings` table) |
| **Webhooks** | `document.processed` events POST to registered URLs with HMAC-SHA256 signatures; delivery attempts recorded (success/failure) in the DB with a health view |

## Technology stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2
- **AI/NLP:** provider abstraction (`LLMProvider`), deterministic heuristic provider (offline default), OpenAI provider, scikit-learn TF-IDF for embeddings/similarity
- **Documents/OCR:** pypdf, python-docx, Pillow + pytesseract (Tesseract optional)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **DB:** PostgreSQL (prod) / SQLite (local default), Redis optional for external workers

---

## Quick start (local, without Docker)

Prerequisites: Python 3.11+, Node 20+. No database server needed (SQLite).

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# → API on http://localhost:8000, docs on http://localhost:8000/docs

# 2) Frontend
cd ../frontend
npm install
npm run build        # served by FastAPI at http://localhost:8000/
# or `npm run dev`   # dev server on :5173 with API proxy to :8000

# 3) Sign in
#    http://localhost:8000 → admin@idp.dev / admin1234
```

Everything works offline (the default `mock` AI provider performs real
heuristic extraction — no API keys required).

## Environment variables

Copy `backend/.env.example` → `backend/.env` (never commit real secrets).

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev value | JWT signing key — change in prod |
| `DATABASE_URL` | `sqlite:///./idp.db` | PostgreSQL in prod |
| `AI_PROVIDER` | `mock` | `mock` (offline) or `openai` |
| `AI_API_KEY` | — | key for the OpenAI provider |
| `UPLOAD_DIR` | `./uploads` | storage outside the web root |
| `MAX_FILE_SIZE_MB` | `10` | upload cap |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.80` | below → `needs_review` |
| `DUPLICATE_SIMILARITY_THRESHOLD` | `0.90` | Level-3 duplicate flag |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@idp.dev` / `admin1234` | first-run bootstrap |

## Database setup & migrations

Dev startup auto-creates tables; production uses Alembic:

```bash
cd backend
alembic upgrade head               # apply migrations
alembic revision --autogenerate -m "change"   # new migration after model edits
```

Schema (normalized): `users`, `documents`, `candidates`, `skills`,
`candidate_skills`, `skill_aliases`, `experiences`, `education`,
`certifications`, `projects`, `jobs`, `skill_match_results`,
`processing_logs`, `audit_logs` — with foreign keys, indexes on query columns,
and cascade deletes where appropriate.

## Running the application

| Component | Command |
|---|---|
| API server | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Frontend (prod) | `cd frontend && npm run build` (served by FastAPI at `/`) |
| Frontend (dev) | `cd frontend && npm run dev` |
| Tests | `cd backend && pytest` |
| Sample data | `cd backend && python scripts/generate_samples.py` |
| Quality eval | `cd backend && python scripts/evaluate.py` |

Processing runs as background tasks inside the API process (async from the
HTTP response; status is polled via `GET /documents/{id}/status`). The
worker entry-point (`process_document_task`) is Celery-compatible, so wiring
an external worker later is a configuration change, not a rewrite.

## API documentation

Interactive OpenAPI docs with request/response schemas, errors and auth
requirements: **http://localhost:8000/docs** (and `/redoc`).

Key endpoints (all under `/api/v1`, JWT required):

```
POST /auth/register|login            GET /auth/me
POST /documents/upload               GET  /documents            (paged, filters)
GET  /documents/{id}                 GET  /documents/{id}/status
POST /documents/{id}/process|retry   POST /documents/{id}/review
GET  /documents/{id}/extraction      GET  /documents/{id}/file   (authorized)
GET  /candidates/search?q&skill&location&degree&min_experience&status&tag
GET  /candidates/semantic-search?q=…  GET  /candidates/export.csv
GET  /candidates/{id}                PUT  /candidates/{id}       (audited)
PUT  /candidates/{id}/status         POST /candidates/{id}/notes
POST|DELETE /candidates/{id}/tags    POST /auth/change-password
GET|POST /skills                     GET|POST /skills/aliases
POST /jobs                           POST /jobs/{id}/match       (weighted: required + nice-to-have)
GET  /analytics/overview|documents|skills|candidates
GET  /admin/processing-logs|audit-logs|config|webhook-deliveries
GET|PUT /admin/settings              GET|POST|PUT|DELETE /admin/webhooks
```

Responses are uniform — success: `{success, data, message}`;
error: `{success: false, error: {code, message}}`.

## AI configuration

```python
class LLMProvider(ABC):
    def extract_resume(self, text: str) -> ExtractionResult: ...
    def classify_document(self, text: str) -> DocumentClassification: ...
```

- **`mock` (default):** deterministic heuristic engine (regex, section parsing,
  canonical skill dictionary). Zero cost, fully offline, reproducible — used by
  the test-suite and demos. Extraction is honest by construction: unavailable
  data stays null/empty.
- **`openai`:** sends the strict prompts from `app/ai/prompts.py` (never invent
  data; JSON only), then validates the response through the same Pydantic
  schemas, with safe-parse + one retry; persistent failure marks the stage
  failed — nothing unvalidated is stored.

Switch with `AI_PROVIDER=openai AI_API_KEY=sk-…`. Add a new provider in ~40
lines by implementing the abstract class and registering it in
`app/ai/factory.py`.

## Testing

```bash
cd backend && pytest -q        # 68 tests
```

- **Unit:** file validation/size/MIME/path-traversal, hashing, per-format
  extraction (incl. corrupted files), normalization/aliases, all three
  duplicate levels, match formula, classification incl. threshold routing
- **AI:** malformed output (invalid JSON, missing fields, wrong types,
  out-of-range confidence) rejected — always against the same schemas,
  no external API required
- **API/e2e:** register/login, wrong password, 401/403 RBAC (viewer can't
  upload/delete), upload→process→retrieve with stage trace, exact-duplicate
  re-upload, search, job match with expected percentages, analytics

## Evaluation dataset

`sample_dataset/` (regenerate with `scripts/generate_samples.py`):
5 resumes, 2 invoices, 2 contracts, 2 certificates, 1 corrupted PDF,
2 scanned (image-only) PDFs, 2 duplicate resumes + `expected_outputs.json`.

`scripts/evaluate.py` measures the deterministic provider:

```
name accuracy: 5/5 = 100%     email accuracy: 100%     phone accuracy: 100%
years accuracy: 100%          degree accuracy: 100%
skills: precision=92% recall=100% F1=96%
```

## Docker

```bash
docker compose up --build
# API:        http://localhost:8000  (and /docs)
# Frontend:   http://localhost:5173  (nginx, proxies /api → backend)
```

Services: `backend`, `frontend`, `postgres`, `redis`, `worker` (placeholder
that documents the Celery seam; in-process background tasks are the default).
The backend image installs Tesseract, so OCR works inside Docker even when
the host lacks it.

## Deploy to Render (free)

The repo ships a `render.yaml` **Blueprint** — Render provisions the web
service and a free PostgreSQL database for you:

1. Push this folder to a GitHub repository (the built `frontend/dist/` is
   committed on purpose, so no Node build is needed on Render).
2. In the Render dashboard: **New → Blueprint →** pick the repo → **Apply**.
3. When prompted, set `ADMIN_PASSWORD` (the admin login for the deployed app).
4. Wait ~3–5 minutes. Your app is live at `https://idp-system.onrender.com`
   (frontend + API same-origin; `/docs` has OpenAPI; `/health` is the check).

On startup the app auto-creates the schema and seeds the admin user, so no
migrations are needed. To fill the demo with the sample dataset:

```bash
python scripts/demo_seed.py --base-url https://your-app.onrender.com
```

Free-tier notes: the instance sleeps after ~15 min idle (first request takes
~30–60 s to wake), uploaded *files* live on ephemeral storage (metadata stays
in Postgres), and free PostgreSQL expires after 90 days. For production, use
a paid disk/persistent volume for `UPLOAD_DIR` and set `AI_PROVIDER=openai`
with your `AI_API_KEY` in the dashboard.

## Security model

- Server-generated storage filenames; originals sanitized and never trusted
- Uploads stored outside any publicly served directory; downloads are
  authorized API calls, not public URLs
- Extension + MIME + size validation, SHA-256 dedupe, path-traversal guards
- All SQL through SQLAlchemy parameterization; React escapes rendered text (XSS-safe)
- bcrypt password hashing, short-lived JWTs, role/permission map in `app/api/deps.py`
- Secrets via env; `.env` files are gitignored; errors never expose stack traces

## Human review & audit

Low classification confidence, low extraction confidence, or high duplicate
similarity → `needs_review`. The document page exposes **Approve / Reject**,
and the candidate page an **Edit & review** form. Every upload, retry, review,
edit and admin change lands in `audit_logs` (user, action, entity, old/new
value, timestamp).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `422 FILE_VALIDATION_FAILED` | unsupported extension/MIME, oversize, or empty file |
| Image/scanned docs fail with "OCR produced no text" | install `tesseract-ocr` (present in the Docker image) |
| Login 422 on seeded admin | you changed `ADMIN_EMAIL` to a reserved TLD like `.local` — email-validator rejects those |
| Everything 401 | token expired; log in again |
| Migration conflicts | dev DB is disposable: `rm backend/idp.db` and restart |
| Port busy | `uvicorn ... --port 8001` and set `VITE_API_URL` for the SPA |

## Project structure

```
idp-system/
├── backend/
│   ├── app/
│   │   ├── main.py · config.py
│   │   ├── api/          auth, documents, candidates, jobs, analytics, admin, deps
│   │   ├── models/       user, document(+logs, audit), profile, matching
│   │   ├── schemas/      common, extraction (AI contracts), api
│   │   ├── services/     pipeline, document/extraction/classification/duplicate/
│   │   │                 skill_matching/normalization/analytics, skill_data
│   │   ├── extractors/   pdf, docx, txt, image, ocr, registry
│   │   ├── ai/           LLMProvider ABC, mock+openai providers, prompts, factory
│   │   ├── repositories/ document/candidate queries
│   │   ├── utils/        security, file_storage, text
│   │   └── database/     engine/session/Base
│   ├── alembic/          migrations (initial schema)
│   ├── tests/            55 tests (unit + API + AI-validation)
│   ├── scripts/          generate_samples.py, evaluate.py
│   ├── Dockerfile · requirements.txt · .env.example
├── frontend/
│   ├── src/pages/        Dashboard, Upload, Documents(+Detail), Candidates(+Detail),
│   │                     Jobs, JobMatch, Analytics, Settings, Login
│   ├── src/components · layouts · hooks · services · types
│   └── Dockerfile (+nginx.conf) · vite.config.ts
├── sample_dataset/       + expected_outputs.json
├── docs/ARCHITECTURE.md
└── docker-compose.yml
```
