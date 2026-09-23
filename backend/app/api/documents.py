"""Document endpoints: upload, list, detail, process, status, review, delete.

Uploads are validated synchronously and processing runs in the background;
status polling happens through GET /documents/{id}/status.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_permission
from app.database.session import get_db
from app.models.document import AuditLog, Document, ProcessingLog, ProcessingStatus
from app.models.user import User
from app.schemas.api import (
    ClassificationOut,
    DocumentOut,
    ExtractionPayloadOut,
    ProcessingLogOut,
    ReviewAction,
)
from app.schemas.common import APIResponse
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService
from app.services.pipeline import process_document_task
from app.utils.file_storage import FileValidationError

router = APIRouter(prefix="/documents", tags=["documents"])


def _out(doc: Document) -> dict:
    return DocumentOut.model_validate(doc).model_dump(mode="json")


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Validates extension/MIME/size, computes SHA-256, stores the file "
    "under a generated name, and queues background processing. "
    "An exact SHA-256 duplicate returns the original record (202 semantics).",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("upload")),
) -> APIResponse:
    service = DocumentService(db)
    try:
        document, is_exact_dup = await service.register_upload(file, user.id)
    except FileValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "FILE_VALIDATION_FAILED", "message": str(exc)},
        ) from exc

    if not is_exact_dup:
        background_tasks.add_task(process_document_task, document.id)
    return APIResponse(
        data={
            "document": _out(document),
            "exact_duplicate": is_exact_dup,
        },
        message="Exact duplicate of an existing document." if is_exact_dup
        else "Document uploaded and queued for processing.",
    )


@router.get("", summary="List documents (paginated, filterable)")
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    document_type: str | None = None,
    duplicates_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    repo = DocumentRepository(db)
    items, total = repo.paginate(page, page_size, status_filter, document_type, duplicates_only)
    return APIResponse(
        data=repo.page_dict([_out(d) for d in items], total, page, page_size)
    )


@router.get("/{document_id}", summary="Document detail",
            description="Metadata, classification, extracted info and duplicate report.")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    return APIResponse(data=_out(doc))


@router.get("/{document_id}/status", summary="Processing status and stage trace")
def document_status(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    doc = (
        db.query(Document)
        .options(joinedload(Document.logs))
        .filter(Document.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    return APIResponse(data={
        "id": doc.id,
        "processing_status": doc.processing_status,
        "processing_error": doc.processing_error,
        "logs": [ProcessingLogOut.model_validate(l).model_dump(mode="json") for l in doc.logs],
    })


@router.get("/{document_id}/classification", summary="Classification result")
def get_classification(
    document_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> ClassificationOut:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    return ClassificationOut(
        document_type=doc.document_type, confidence=doc.classification_confidence
    )


@router.get("/{document_id}/extraction", summary="Extracted structured information")
def get_extraction(
    document_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("read")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    cand = doc.candidate
    payload = ExtractionPayloadOut(
        candidate={
            "name": cand.name, "email": cand.email, "phone": cand.phone,
            "location": cand.location, "linkedin": cand.linkedin, "github": cand.github,
            "portfolio": cand.portfolio,
            "professional_summary": cand.professional_summary,
        } if cand else None,
        skills=sorted({cs.skill.name for cs in cand.skills}) if cand else [],
        experiences=[{"company": e.company, "job_title": e.job_title,
                      "description": e.description} for e in cand.experiences] if cand else [],
        education=[{"institution": e.institution, "degree": e.degree,
                    "field": e.field, "end_year": e.end_year} for e in cand.educations] if cand else [],
        certifications=[{"name": c.name, "issuer": c.issuer} for c in cand.certifications] if cand else [],
        projects=[{"name": p.name, "description": p.description} for p in cand.projects] if cand else [],
        total_experience_years=cand.total_experience_years if cand else None,
    )
    return APIResponse(data=payload.model_dump(mode="json"))


@router.get("/{document_id}/file", summary="Download the original file (authorized)")
def download_file(
    document_id: int, db: Session = Depends(get_db),
    _: User = Depends(require_permission("file_download")),
) -> FileResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(404, detail={"code": "FILE_MISSING", "message": "Stored file missing."})
    return FileResponse(path, filename=doc.filename)


@router.post("/{document_id}/process", summary="Queue (re)processing")
def process_document(
    document_id: int, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("process")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    if doc.processing_status in (ProcessingStatus.QUEUED, ProcessingStatus.EXTRACTING,
                                 ProcessingStatus.CLASSIFYING, ProcessingStatus.PROCESSING):
        return APIResponse(data=_out(doc), message="Already being processed.")
    doc.processing_status = ProcessingStatus.QUEUED
    doc.processing_error = None
    db.commit()
    background_tasks.add_task(process_document_task, document_id)
    return APIResponse(data=_out(doc), message="Processing queued.")


@router.post("/{document_id}/retry", summary="Retry a failed document")
def retry_document(
    document_id: int, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("retry")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    db.add(AuditLog(user_id=user.id, action="retry_processing", entity="document",
                    entity_id=doc.id, old_value=doc.processing_status))
    doc.processing_status = ProcessingStatus.QUEUED
    doc.processing_error = None
    db.commit()
    background_tasks.add_task(process_document_task, document_id)
    return APIResponse(message="Retry queued.")


@router.post("/{document_id}/review", summary="Approve or reject a needs_review document",
             description="Human review outcome is recorded with reviewer and timestamp.")
def review_document(
    document_id: int, action: ReviewAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("review")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    from datetime import datetime, timezone

    doc.reviewed_by = user.id
    doc.reviewed_at = datetime.now(timezone.utc)
    if action.action == "approve":
        doc.processing_status = ProcessingStatus.COMPLETED
        doc.processing_error = None
    elif action.action == "reject":
        doc.processing_status = ProcessingStatus.FAILED
        doc.processing_error = "Rejected during human review."
    else:
        raise HTTPException(400, detail={"code": "BAD_ACTION",
                                         "message": "action must be 'approve' or 'reject'."})
    db.add(AuditLog(user_id=user.id, action=f"review_{action.action}", entity="document",
                    entity_id=doc.id, new_value=action.notes))
    db.commit()
    return APIResponse(data=_out(doc), message=f"Review '{action.action}' recorded.")


@router.delete("/{document_id}", summary="Delete a document + stored file")
def delete_document(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(require_permission("delete")),
) -> APIResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Document not found."})
    Path(doc.file_path).unlink(missing_ok=True)
    db.add(AuditLog(user_id=user.id, action="delete_document", entity="document",
                    entity_id=doc.id, old_value=doc.filename))
    db.delete(doc)
    db.commit()
    return APIResponse(message="Document deleted.")
