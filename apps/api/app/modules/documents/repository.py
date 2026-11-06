"""Document and job queries. Every function takes `workspace_id` so no query can cross a
workspace boundary by omission (SEC-03)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Document, IngestionJob
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
