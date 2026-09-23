"""Unit tests: secure file upload validation, hashing, filename sanitization."""
import hashlib

import pytest

from app.utils.file_storage import (
    FileValidationError,
    sanitize_filename,
    sha256_hex,
    store_file,
    validate_upload,
)


def test_validate_accepts_supported_types():
    data = b"hello world"
    assert validate_upload("resume.pdf", "application/pdf", data) == ".pdf"
    assert validate_upload("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", data) == ".docx"
    assert validate_upload("notes.txt", "text/plain", data) == ".txt"
    assert validate_upload("photo.png", "image/png", data) == ".png"


@pytest.mark.parametrize("name", ["evil.exe", "script.sh", "archive.zip", "noext"])
def test_validate_rejects_unsupported_extensions(name):
    with pytest.raises(FileValidationError):
        validate_upload(name, "application/octet-stream", b"x")


def test_validate_rejects_wrong_mime():
    with pytest.raises(FileValidationError):
        validate_upload("resume.pdf", "application/x-msdownload", b"x")


def test_validate_rejects_oversize(settings_mb: int = 10):
    big = b"0" * (settings_mb * 1024 * 1024 + 1)
    with pytest.raises(FileValidationError):
        validate_upload("resume.pdf", "application/pdf", big)


def test_validate_rejects_empty_file():
    with pytest.raises(FileValidationError):
        validate_upload("resume.pdf", "application/pdf", b"")


def test_sha256_matches_stdlib():
    data = b"document-bytes"
    assert sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_sanitize_filename_strips_traversal_and_weird_chars():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\win\\system32\\x.dll") == "x.dll"
    assert "/" not in sanitize_filename("a/b/c.pdf")
    assert sanitize_filename("résumé final (2).pdf").endswith(".pdf")


def test_store_file_generates_unique_names_inside_upload_dir(tmp_path):
    from app.config import settings

    name1, path1 = store_file(b"a", ".txt")
    name2, path2 = store_file(b"a", ".txt")
    assert name1 != name2
    assert str(path1.resolve()).startswith(str(settings.UPLOAD_DIR.resolve()))
    assert path1.exists()
