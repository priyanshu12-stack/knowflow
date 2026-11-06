"""Knowledge Library endpoints (TRD §8): upload, list, detail, delete."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, SettingsDep, StorageDep, WorkspaceDep
from app.core.errors import AppError, ErrorResponse
from app.db.models import Document
from app.modules.documents import repository, service
from app.modules.documents.status import DocumentStatus
from app.modules.documents.validation import SUPPORTED_FORMATS
from app.schemas.common import Page, PageParams, page_params
from app.schemas.documents import (
    ChunkOut,
    ChunkStrategy,
    DocumentOut,
    DuplicateAction,
    ExtractionPreviewOut,
    SectionOut,
    SupportedFormatOut,
    UploadPolicyOut,
    UploadResult,
)

router = APIRouter(prefix="/documents", tags=["documents"])

_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (409, 411, 413, 415, 422, 503)
}


def _not_found() -> AppError:
    return AppError("document_not_found", "This document doesn't exist or was deleted.", 404)


@router.get("/upload-policy", response_model=UploadPolicyOut)
def get_upload_policy(settings: SettingsDep) -> UploadPolicyOut:
    """What the upload UI shows before a file is chosen (PRD §5.2)."""
    return UploadPolicyOut(
        max_bytes=settings.upload_max_bytes,
        formats=[
            SupportedFormatOut(
                file_type=f.file_type,
                label=f.label,
                mime_type=f.mime_type,
                extensions=list(f.extensions),
            )
            for f in SUPPORTED_FORMATS
        ],
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResult,
    responses={200: {"model": UploadResult, "description": "Duplicate skipped"}, **_ERRORS},
)
def upload_document(
    response: Response,
    file: Annotated[UploadFile, File(description="PDF (text-based), DOCX, TXT or Markdown")],
    session: SessionDep,
    storage: StorageDep,
    workspace: WorkspaceDep,
    settings: SettingsDep,
    on_duplicate: Annotated[
        DuplicateAction | None,
        Query(description="How to handle identical content. Omit to get a 409 with choices."),
    ] = None,
) -> UploadResult:
    result = service.upload_document(
        session,
        storage,
        workspace,
        filename=file.filename,
        declared_mime=file.content_type,
        source=file.file,
        max_bytes=settings.upload_max_bytes,
        on_duplicate=on_duplicate,
    )
    if result.outcome == "skipped":
        response.status_code = status.HTTP_200_OK
    latest = result.job or repository.latest_jobs(session, [result.document.id]).get(
        result.document.id
    )
    document = service.to_document_out(result.document, latest)
    return UploadResult(
        outcome=result.outcome,
        document_id=document.id,
        job_id=result.job.id if result.job else None,
        status=document.status,
        document=document,
    )


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    session: SessionDep,
    workspace: WorkspaceDep,
    page: Annotated[PageParams, Depends(page_params)],
    status_filter: Annotated[
        DocumentStatus | None, Query(alias="status", description="Only documents in this state")
    ] = None,
) -> Page[DocumentOut]:
    rows, total = repository.list_documents(
        session, workspace.id, limit=page.limit, offset=page.offset, status=status_filter
    )
    ids = [d.id for d in rows]
    jobs = repository.latest_jobs(session, ids)
    counts = repository.chunk_counts(session, ids)
    return Page(
        items=[service.to_document_out(d, jobs.get(d.id), counts.get(d.id, 0)) for d in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{document_id}", response_model=DocumentOut, responses={404: {"model": ErrorResponse}})
def get_document(
    document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> DocumentOut:
    document = repository.get_document(session, workspace.id, document_id)
    if document is None:
        raise _not_found()
    return _document_out(session, document)


def _document_out(session: Session, document: Document) -> DocumentOut:
    job = repository.latest_jobs(session, [document.id]).get(document.id)
    count = repository.chunk_counts(session, [document.id]).get(document.id, 0)
    return service.to_document_out(document, job, count)


@router.post(
    "/{document_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentOut,
    responses={404: {"model": ErrorResponse}},
)
def retry_document(
    document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> DocumentOut:
    """Queue processing again (failed ingestion, or a manual re-index). Idempotent."""
    document = repository.get_document(session, workspace.id, document_id)
    if document is None:
        raise _not_found()
    service.retry_document(session, document)
    return _document_out(session, document)


@router.get(
    "/{document_id}/chunks",
    response_model=Page[ChunkOut],
    responses={404: {"model": ErrorResponse}},
)
def list_chunks(
    document_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
    page: Annotated[PageParams, Depends(page_params)],
    strategy: Annotated[ChunkStrategy, Query(description="Chunking strategy")] = "recursive",
) -> Page[ChunkOut]:
    """Chunk inspection (PRD §5.2, DRD §7.2 document drawer)."""
    if repository.get_document(session, workspace.id, document_id) is None:
        raise _not_found()
    rows, total = repository.list_chunks(
        session, workspace.id, document_id, strategy=strategy, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[ChunkOut.model_validate(c) for c in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{document_id}/extraction",
    response_model=ExtractionPreviewOut,
    responses={404: {"model": ErrorResponse}},
)
def extraction_preview(
    document_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    max_chars: Annotated[int, Query(ge=100, le=5000)] = 1500,
) -> ExtractionPreviewOut:
    """The first extracted pages/sections, truncated, for the document drawer preview."""
    if repository.get_document(session, workspace.id, document_id) is None:
        raise _not_found()
    rows, total = repository.list_sections(session, workspace.id, document_id, limit=limit)
    return ExtractionPreviewOut(
        total_sections=total,
        sections=[
            SectionOut(
                ordinal=r.ordinal,
                page_number=r.page_number,
                section_path=r.section_path,
                text=r.text if len(r.text) <= max_chars else r.text[:max_chars].rstrip() + " …",
            )
            for r in rows
        ],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID, session: SessionDep, storage: StorageDep, workspace: WorkspaceDep
) -> Response:
    """Idempotent: deleting a missing (or foreign-workspace) document also returns 204."""
    service.delete_document(session, storage, workspace.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
