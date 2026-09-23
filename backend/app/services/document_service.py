"""Document upload orchestration: validate -> hash -> dedupe -> store -> record."""
from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.document import AuditLog, Document, ProcessingStatus
from app.services.duplicate_service import DuplicateService
from app.utils.file_storage import (
    FileValidationError,
    sanitize_filename,
    sha256_hex,
    store_file,
    validate_upload,
)


class DocumentService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._duplicates = DuplicateService(db)

    async def register_upload(
        self, upload: UploadFile, user_id: int | None
    ) -> tuple[Document, bool]:
        """Validate + store an upload. Returns (document, was_exact_duplicate)."""
        original = sanitize_filename(upload.filename or "upload")
        data = await upload.read()  # size-capped by validate_upload below
        ext = validate_upload(original, upload.content_type, data)
        file_hash = sha256_hex(data)

        # Level-1 duplicate: reuse the existing document record, keep a trace.
        exact = self._duplicates.check_exact_file(file_hash)
        if exact.is_duplicate and exact.matched_document_id:
            existing = self._db.get(Document, exact.matched_document_id)
            if existing is not None:
                self._db.add(AuditLog(
                    user_id=user_id, action="upload_exact_duplicate",
                    entity="document", entity_id=existing.id,
                    new_value=f"re-uploaded as '{original}'",
                ))
                self._db.commit()
                return existing, True

        stored_name, path = store_file(data, ext)
        document = Document(
            filename=original,
            stored_filename=stored_name,
            file_path=str(path),
            file_type=ext,
            file_size=len(data),
            file_hash=file_hash,
            processing_status=ProcessingStatus.QUEUED,
            uploaded_by=user_id,
        )
        self._db.add(document)
        self._db.add(AuditLog(
            user_id=user_id, action="upload_document", entity="document",
            new_value=original,
        ))
        self._db.flush()
        document_id = document.id
        self._db.commit()
        self._db.refresh(document)
        assert document.id == document_id
        return document, False
