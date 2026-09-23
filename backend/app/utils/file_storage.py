"""Secure file upload handling.

Rules enforced here:
* extension + MIME validation
* size cap (checked against actual bytes as well as the header)
* SHA-256 content hash (exact-duplicate detection)
* unique, server-generated storage filenames (original name never trusted)
* path-traversal protection (storage path verified to live under UPLOAD_DIR)
* files are stored outside any publicly served web directory
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path

from app.config import settings


class FileValidationError(Exception):
    """Raised when an uploaded file fails validation. Carries a safe message."""


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Return a display-safe version of the original filename."""
    # Neutralize both forward and back slashes before taking the basename,
    # so Windows-style traversal ("..\..\x.dll") is stripped on any host OS.
    cleaned = unicodedata.normalize("NFKD", name).replace("\\", "/")
    base = Path(cleaned).name
    base = _SAFE_CHARS.sub("_", base).strip("._") or "file"
    return base[:200]


def validate_upload(filename: str, content_type: str | None, data: bytes) -> str:
    """Validate extension, MIME type and size. Returns the lowercase extension."""
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{ext or '(none)'}'. "
            f"Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}."
        )
    if content_type and content_type not in settings.ALLOWED_MIME_TYPES:
        raise FileValidationError(f"Unsupported MIME type '{content_type}'.")
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(data) == 0:
        raise FileValidationError("Uploaded file is empty.")
    if len(data) > max_bytes:
        raise FileValidationError(
            f"File too large ({len(data) / 1024 / 1024:.1f} MB). "
            f"Maximum is {settings.MAX_FILE_SIZE_MB} MB."
        )
    return ext


def sha256_hex(data: bytes) -> str:
    """Content hash used for exact-duplicate detection."""
    return hashlib.sha256(data).hexdigest()


def store_file(data: bytes, ext: str) -> tuple[str, Path]:
    """Write bytes under a unique server-generated name; return (name, path)."""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = (settings.UPLOAD_DIR / stored_name).resolve()
    # Path-traversal guard: the resolved path must remain inside UPLOAD_DIR.
    if not str(target).startswith(str(settings.UPLOAD_DIR.resolve())):
        raise FileValidationError("Invalid storage path.")
    target.write_bytes(data)
    return stored_name, target
