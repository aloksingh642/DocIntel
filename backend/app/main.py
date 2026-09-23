"""FastAPI application entry-point.

* OpenAPI docs at /docs and /redoc (fully described endpoints).
* Consistent JSON error envelope for every controlled failure.
* Serves the built frontend (frontend/dist) at / when present.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, analytics, auth, candidates, documents, jobs
from app.config import settings
from app.database.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("idp")


def error_envelope(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"success": False, "error": {"code": code, "message": message}},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Intelligent Document Processing System",
        description=(
            "AI-powered pipeline: upload -> extract -> classify -> structured "
            "extraction -> normalize -> duplicate detection -> skill matching -> "
            "analytics. All AI output is schema-validated; nothing is invented."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://doc-intel-peach.vercel.app", "http://localhost:5173"],  # frontend is served same-origin in prod; widen for dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- consistent error handling --------------------------------------
    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return error_envelope(detail["code"], detail.get("message", "Error"), exc.status_code)
        return error_envelope("HTTP_ERROR", str(detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = " -> ".join(str(p) for p in first.get("loc", []))
        return error_envelope(
            "VALIDATION_ERROR",
            f"Invalid request ({field}): {first.get('msg', 'check the request body.')}",
            422,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        # Stack traces stay in server logs — never leak to clients.
        return error_envelope("INTERNAL_ERROR", "An unexpected server error occurred.", 500)

    # ---- routes ----------------------------------------------------------
    prefix = settings.API_PREFIX
    app.include_router(auth.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(candidates.router, prefix=prefix)
    app.include_router(jobs.router, prefix=prefix)
    app.include_router(analytics.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)

    @app.get("/health", tags=["ops"], summary="Liveness + dependency check")
    def health() -> dict:
        from app.extractors.ocr import tesseract_available

        return {
            "status": "ok",
            "ai_provider": settings.AI_PROVIDER,
            "ocr_available": tesseract_available(),
            "database": "postgresql" if "postgres" in settings.DATABASE_URL else "sqlite",
        }

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        _seed_default_admin()
        logger.info("IDP backend started (provider=%s)", settings.AI_PROVIDER)

    # ---- built frontend (same-origin deployment) --------------------------
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


def _seed_default_admin() -> None:
    """Bootstrap an admin on first run so the demo is immediately usable."""
    from app.database.session import SessionLocal
    from app.models.user import User
    from app.utils.security import hash_password

    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == settings.ADMIN_EMAIL).first() is None:
            db.add(User(
                name="Administrator",
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            ))
            db.commit()
            logger.info("Seeded default admin: %s", settings.ADMIN_EMAIL)
    finally:
        db.close()


app = create_app()
