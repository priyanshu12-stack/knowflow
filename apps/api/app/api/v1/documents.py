"""Knowledge Library endpoints (TRD §8): upload, list, detail, delete."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import SessionDep, SettingsDep, StorageDep, WorkspaceDep
from app.core.errors import AppError, ErrorResponse
from app.modules.documents import repository, service
from app.modules.documents.validation import SUPPORTED_FORMATS
from app.schemas.common import Page, PageParams, page_params
from app.schemas.documents import (
    DocumentOut,
    DuplicateAction,
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
) -> Page[DocumentOut]:
    rows, total = repository.list_documents(
        session, workspace.id, limit=page.limit, offset=page.offset
    )
    jobs = repository.latest_jobs(session, [d.id for d in rows])
    return Page(
        items=[service.to_document_out(d, jobs.get(d.id)) for d in rows],
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
    job = repository.latest_jobs(session, [document.id]).get(document.id)
    return service.to_document_out(document, job)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID, session: SessionDep, storage: StorageDep, workspace: WorkspaceDep
) -> Response:
    """Idempotent: deleting a missing (or foreign-workspace) document also returns 204."""
    service.delete_document(session, storage, workspace.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
