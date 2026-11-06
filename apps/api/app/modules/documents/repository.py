"""Document and job queries. Every function takes `workspace_id` so no query can cross a
workspace boundary by omission (SEC-03)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentSection, IngestionJob
from app.modules.documents.status import ACTIVE_JOB_STATUSES


def get_document(
    session: Session, workspace_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    return session.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )


def list_documents(
    session: Session,
    workspace_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    status: str | None = None,
) -> tuple[Sequence[Document], int]:
    conditions = [Document.workspace_id == workspace_id]
    if status is not None:
        conditions.append(Document.status == status)
    total = session.scalar(select(func.count()).select_from(Document).where(*conditions))
    rows = session.scalars(
        select(Document)
        .where(*conditions)
        .order_by(Document.created_at.desc(), Document.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return rows, total or 0


def find_by_checksum(session: Session, workspace_id: uuid.UUID, sha256: str) -> Sequence[Document]:
    """All versions with this content, newest version first."""
    return session.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id, Document.sha256 == sha256)
        .order_by(Document.version.desc())
    ).all()


def latest_jobs(
    session: Session, document_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, IngestionJob]:
    if not document_ids:
        return {}
    jobs = session.scalars(
        select(IngestionJob)
        .where(IngestionJob.document_id.in_(document_ids))
        .distinct(IngestionJob.document_id)
        .order_by(IngestionJob.document_id, IngestionJob.created_at.desc())
    ).all()
    return {job.document_id: job for job in jobs}


def active_job(session: Session, document_id: uuid.UUID) -> IngestionJob | None:
    return session.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.document_id == document_id,
            IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )


def get_job(session: Session, workspace_id: uuid.UUID, job_id: uuid.UUID) -> IngestionJob | None:
    return session.scalar(
        select(IngestionJob)
        .join(Document, Document.id == IngestionJob.document_id)
        .where(IngestionJob.id == job_id, Document.workspace_id == workspace_id)
    )


# Chunk counts shown in the library use the default retrieval strategy (recursive, ADR-005).
DEFAULT_STRATEGY = "recursive"


def chunk_counts(
    session: Session, document_ids: Sequence[uuid.UUID], strategy: str = DEFAULT_STRATEGY
) -> dict[uuid.UUID, int]:
    if not document_ids:
        return {}
    rows = session.execute(
        select(Chunk.document_id, func.count())
        .where(Chunk.document_id.in_(document_ids), Chunk.strategy == strategy)
        .group_by(Chunk.document_id)
    ).all()
    return {doc_id: count for doc_id, count in rows}


def list_chunks(
    session: Session,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    strategy: str,
    limit: int,
    offset: int,
) -> tuple[Sequence[Chunk], int]:
    conditions = [
        Chunk.workspace_id == workspace_id,
        Chunk.document_id == document_id,
        Chunk.strategy == strategy,
    ]
    total = session.scalar(select(func.count()).select_from(Chunk).where(*conditions))
    rows = session.scalars(
        select(Chunk).where(*conditions).order_by(Chunk.chunk_index).limit(limit).offset(offset)
    ).all()
    return rows, total or 0


def list_sections(
    session: Session, workspace_id: uuid.UUID, document_id: uuid.UUID, *, limit: int
) -> tuple[Sequence[DocumentSection], int]:
    conditions = [
        DocumentSection.workspace_id == workspace_id,
        DocumentSection.document_id == document_id,
    ]
    total = session.scalar(select(func.count()).select_from(DocumentSection).where(*conditions))
    rows = session.scalars(
        select(DocumentSection).where(*conditions).order_by(DocumentSection.ordinal).limit(limit)
    ).all()
    return rows, total or 0
