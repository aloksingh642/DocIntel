"""Application configuration loaded from environment variables.

All configuration is environment-driven; secrets never live in code.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Typed settings with sensible local-development defaults."""

    def __init__(self) -> None:
        # Core
        self.APP_NAME: str = os.getenv("APP_NAME", "Intelligent Document Processing System")
        self.ENV: str = os.getenv("ENV", "development")
        self.API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")

        # Security
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-change-me-in-production")
        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

        # Database — SQLite by default so the project runs locally with zero setup;
        # point DATABASE_URL at PostgreSQL in deployed environments.
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'idp.db'}"
        )
        # Render/Heroku-style URLs start with "postgres://" which SQLAlchemy rejects.
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = "postgresql://" + self.DATABASE_URL[len("postgres://"):]

        # Redis / Celery (optional; when absent the in-process background queue is used)
        self.REDIS_URL: str = os.getenv("REDIS_URL", "")

        # AI provider: "mock" (deterministic, offline, default) or "openai"
        self.AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")
        self.AI_API_KEY: str = os.getenv("AI_API_KEY", "")
        self.AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")

        # File storage
        self.UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
        self.MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
        self.ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
        self.ALLOWED_MIME_TYPES: set[str] = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "image/jpeg",
            "image/png",
        }

        # Pipeline thresholds
        self.CLASSIFICATION_CONFIDENCE_THRESHOLD: float = float(
            os.getenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.80")
        )
        self.DUPLICATE_SIMILARITY_THRESHOLD: float = float(
            os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.90")
        )

        # Auth bootstrap (first-run admin creation)
        self.ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@idp.dev")
        self.ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin1234")

        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
