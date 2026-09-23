# Architecture notes

## Design drivers

1. **Correctness of AI output.** Everything produced by an AI/ML component is
   validated against Pydantic contracts (`schemas/extraction.py`) before
   persistence. Unparsable output triggers one retry; persistent failure
   marks the stage failed. Nothing unvalidated is stored, and the UI labels
   values as *extracted, not verified*.
2. **Replaceability.** The AI provider, the classifier, and each extractor
   implement narrow abstract contracts and are wired through small factories
   (`ai/factory.py`, `extractors/__init__.py`). Swapping the provider is an
   env var; adding a document type is one module + one registry entry.
3. **Failure isolation.** Each pipeline stage is wrapped by a timing/logging
   context manager that persists a `ProcessingLog` row on both success and
   failure, so any document carries a complete forensic trace.
4. **Local-first operator experience.** SQLite + in-process background tasks
   + offline AI provider mean a single `uvicorn` command demonstrates the
   entire system; PostgreSQL/Redis/external workers are deployment concerns
   handled by configuration.

## Pipeline state machine

```
uploaded → queued → extracting → classifying → processing
             → duplicate_check → completed | needs_review | failed
```

- `needs_review` when: classification confidence < threshold (0.80),
  extraction confidence < threshold, or Level-3 duplicate suspected.
- `failed` when: any stage raised (`processing_error` carries a
  stage-prefixed, user-safe message; the stack trace stays in server logs).

## Duplicate detection

| Level | Signal | Where |
|---|---|---|
| 1 — exact | SHA-256 of file bytes | `DocumentService.register_upload` |
| 2 — identity | normalized email → phone → name match | `DuplicateService.find_candidate` |
| 3 — content | TF-IDF (1–2 grams, 8k features) cosine ≥ threshold | `DuplicateService.check_content_similarity` |

Suspects are flagged with `duplicate_type`, `similarity`, and
`matched_document_id` — deletion is always a human decision.

## Why TF-IDF instead of a heavy embedding model

The similarity check must be fast, offline and reproducible in CI.
TF-IDF + cosine gives deterministic, explainable signals at ~zero cost and
catches near-identical documents (the realistic duplicate case: edits,
renames, format conversion). The service boundary hides the choice, so a
`sentence-transformers` embedder can replace the internals without touching
callers.

## Background work

`POST /documents/upload` validates synchronously, creates the record, and
returns `201` immediately; the pipeline runs through
`BackgroundTasks.add_task(process_document_task, id)` which owns its DB
session. Status transitions are visible through `GET /documents/{id}/status`.
`process_document_task` is the single defined seam for promoting to
Celery + Redis when throughput demands it (see `docker-compose.yml`'s
`worker` service note).

## Data model highlights

- `documents.file_hash` indexed for Level-1 lookups; `extracted_text` feeds
  Level-3 comparisons.
- `skills.normalized_name` unique; `candidate_skills` is a composite-PK
  join with optional proficiency/years for future scoring.
- `skill_aliases` lets administrators steer normalization without deploys
  (seeded from `services/skill_data.DEFAULT_SKILL_ALIASES`).
- `processing_logs` records stage, status, message and seconds; dashboard
  "average processing time" aggregates these.
- `audit_logs` captures user intent for uploads, retries, reviews, edits,
  and admin operations.

## Front-end decisions

- React 18 + TS + Vite; Tailwind via CDN in `index.html` keeps the build
  dependency-light while delivering the design system.
- SPA is built to `frontend/dist` and mounted by FastAPI at `/` — single
  origin, no CORS surface in production; Vite proxy handles dev.
- Recharts drives the dashboard/analytics visualizations; the upload page
  polls `/documents/{id}/status` to render a live stage trace.
