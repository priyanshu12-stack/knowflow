"""Document use cases: upload (with duplicate handling) and delete (ING-05, ING-12, ING-13).

Upload order matters for safety:
1. Cheap checks on name and declared MIME, before reading the body.
2. Stream to an incoming file (hash + size limit), then verify the file signature.
3. Resolve duplicates by SHA-256 within the workspace.
4. Insert document + queued job, move the file into place, commit. If the commit fails the file
   is removed, so a row never points at a missing file and no orphan file is left behind.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import BinaryIO

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Document, IngestionJob, Workspace
from app.modules.documents import repository
from app.modules.documents.storage import FileStorage, make_storage_key
from app.modules.documents.validation import (
    check_declared_mime,
    check_signature,
    format_for_filename,
    sanitize_filename,
)
from app.schemas.documents import DocumentOut, DuplicateAction, JobOut, SafeError, UploadOutcome

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadOutput:
    outcome: UploadOutcome
    document: Document
    job: IngestionJob | None


def to_document_out(document: Document, latest_job: IngestionJob | None) -> DocumentOut:
    last_error = None
    if latest_job is not None and latest_job.status == "failed":
        last_error = SafeError(
            code=latest_job.error_code or "ingestion_failed",
            message=latest_job.error_message_safe or "Processing failed.",
        )
    return DocumentOut.model_validate(
        {
            **{c: getattr(document, c) for c in DocumentOut.model_fields if hasattr(document, c)},
            "chunk_count": None,
            "last_error": last_error,
            "latest_job": JobOut.model_validate(latest_job) if latest_job else None,
        }
    )


def _duplicate_error(existing: Document, latest_job: IngestionJob | None) -> AppError:
    return AppError(
        "duplicate_document",
        f"A document with identical content already exists: {existing.original_name}.",
        409,
        details={
            "existing_document": to_document_out(existing, latest_job).model_dump(mode="json"),
            "choices": ["skip", "reindex", "new_version"],
        },
    )


def _queue_job(session: Session, document: Document) -> IngestionJob:
    job = IngestionJob(id=uuid.uuid4(), document_id=document.id, status="queued")
    session.add(job)
    document.status = "queued"
    return job


def _reindex(session: Session, document: Document) -> IngestionJob:
    """Queue processing again. Idempotent: an already queued/running job is reused."""
    job = repository.active_job(session, document.id)
    if job is None:
        job = _queue_job(session, document)
        session.commit()
    return job


def upload_document(
    session: Session,
    storage: FileStorage,
    workspace: Workspace,
    *,
    filename: str | None,
    declared_mime: str | None,
    source: BinaryIO,
    max_bytes: int,
    on_duplicate: DuplicateAction | None,
) -> UploadOutput:
    name = sanitize_filename(filename)
    fmt = format_for_filename(name)
    check_declared_mime(fmt, declared_mime)

    incoming = storage.receive(source, max_bytes)
    try:
        check_signature(fmt, incoming.path)

        version = 1
        existing = repository.find_by_checksum(session, workspace.id, incoming.sha256)
        if existing:
            newest = existing[0]
            if on_duplicate is None:
                job = repository.latest_jobs(session, [newest.id]).get(newest.id)
                raise _duplicate_error(newest, job)
            if on_duplicate == "skip":
                return UploadOutput("skipped", newest, None)
            if on_duplicate == "reindex":
                return UploadOutput("reindexed", newest, _reindex(session, newest))
            version = newest.version + 1

        document_id = uuid.uuid4()
        document = Document(
            id=document_id,
            workspace_id=workspace.id,
            original_name=name,
            storage_key=make_storage_key(workspace.id, document_id),
            file_type=fmt.file_type,
            mime_type=fmt.mime_type,
            size_bytes=incoming.size_bytes,
            sha256=incoming.sha256,
            version=version,
            status="queued",
        )
        session.add(document)
        job = _queue_job(session, document)
        try:
            session.flush()
        except IntegrityError as exc:
            # Same content uploaded concurrently: the unique (workspace, sha256, version) won.
            session.rollback()
            raise AppError(
                "duplicate_document",
                "The same file was uploaded at the same moment. Refresh the library and retry.",
                409,
            ) from exc

        storage.commit(incoming, document.storage_key)
        try:
            session.commit()
        except Exception:
            session.rollback()
            storage.delete(document.storage_key)
            raise
    finally:
        storage.discard(incoming)  # no-op once the file has been moved into place

    logger.info(
        "document_uploaded",
        extra={
            "document_id": str(document.id),
            "job_id": str(job.id),
            "file_type": fmt.file_type,
            "size_bytes": incoming.size_bytes,
            "version": version,
        },
    )
    return UploadOutput("new_version" if version > 1 else "created", document, job)


def delete_document(
    session: Session, storage: FileStorage, workspace_id: uuid.UUID, document_id: uuid.UUID
) -> bool:
    """Delete metadata, jobs and the stored file. Idempotent; returns whether anything existed.

    The ownership check comes first: a document from another workspace is treated as absent and
    its file is never touched.
    """
    document = repository.get_document(session, workspace_id, document_id)
    if document is None:
        return False
    key = document.storage_key
    session.delete(document)
    session.commit()
    try:
        storage.delete(key)
    except OSError as exc:
        # The row is gone; an undeletable file is logged by id for manual cleanup.
        logger.error(
            "storage_delete_failed",
            extra={"document_id": str(document_id), "error_type": type(exc).__name__},
        )
    logger.info("document_deleted", extra={"document_id": str(document_id)})
    return True
