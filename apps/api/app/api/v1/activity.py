"""Activity / troubleshooting endpoints (PRD §4 Activity, DRD §7.1 key metrics).

Everything here is workspace-scoped and returns ids, statuses, counts and latencies only.
"""

import statistics
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import SessionDep, WorkspaceDep
from app.db.models import (
    AuditEvent,
    Chunk,
    Conversation,
    Document,
    EvaluationRun,
    IngestionJob,
    Message,
    SqlQueryLog,
)

router = APIRouter(prefix="/activity", tags=["activity"])

Category = Literal[
    "all",
    "document",
    "ingestion",
    "chat",
    "conversation",
    "feedback",
    "settings",
    "evaluation",
    "sql",
    "workspace",
]


class EventOut(BaseModel):
    id: str
    created_at: datetime
    actor: str
    action: str
    resource_type: str
    resource_id: str | None
    request_id: str | None
    metadata: dict[str, Any]


class EventPage(BaseModel):
    items: list[EventOut]
    total: int


class JobOut(BaseModel):
    id: str
    document_id: str
    document_name: str
    status: str
    stage: str | None
    attempts: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None


class LatestRun(BaseModel):
    id: str
    label: str
    status: str
    recall_at_k: float | None
    mrr: float | None
    cases: int
    created_at: datetime


class SummaryOut(BaseModel):
    documents: int
    documents_ready: int
    documents_processing: int
    documents_failed: int
    chunks: int
    questions_7d: int
    abstained_7d: int
    answer_latency_p50_ms: float | None
    sql_questions_7d: int
    latest_evaluation: LatestRun | None


@router.get("/events", response_model=EventPage)
def events(
    session: SessionDep,
    workspace: WorkspaceDep,
    category: Category = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    conditions = [AuditEvent.workspace_id == workspace.id]
    if category != "all":
        conditions.append(AuditEvent.action.like(f"{category}.%"))
    total = session.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    rows = session.scalars(
        select(AuditEvent)
        .where(*conditions)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return EventPage(
        total=total,
        items=[
            EventOut(
                id=str(e.id),
                created_at=e.created_at,
                actor=e.actor,
                action=e.action,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                request_id=e.request_id,
                metadata=e.metadata_safe,
            )
            for e in rows
        ],
    )


@router.get("/jobs", response_model=list[JobOut])
def jobs(
    session: SessionDep,
    workspace: WorkspaceDep,
    status: Literal["all", "failed", "active"] = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JobOut]:
    stmt = (
        select(IngestionJob, Document.original_name)
        .join(Document, Document.id == IngestionJob.document_id)
        .where(Document.workspace_id == workspace.id)
    )
    if status == "failed":
        stmt = stmt.where(IngestionJob.status == "failed")
    elif status == "active":
        stmt = stmt.where(IngestionJob.status.in_(("queued", "running")))
    rows = session.execute(stmt.order_by(IngestionJob.created_at.desc()).limit(limit)).all()
    out = []
    for job, name in rows:
        duration = (
            round((job.completed_at - job.started_at).total_seconds() * 1000)
            if job.completed_at and job.started_at
            else None
        )
        out.append(
            JobOut(
                id=str(job.id),
                document_id=str(job.document_id),
                document_name=name,
                status=job.status,
                stage=job.stage,
                attempts=job.attempts,
                error_code=job.error_code,
                error_message=job.error_message_safe,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_ms=duration,
            )
        )
    return out


@router.get("/summary", response_model=SummaryOut)
def summary(session: SessionDep, workspace: WorkspaceDep) -> SummaryOut:
    ws = workspace.id
    counts: dict[str, int] = {
        status: n
        for status, n in session.execute(
            select(Document.status, func.count())
            .where(Document.workspace_id == ws)
            .group_by(Document.status)
        ).all()
    }
    chunks = session.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.workspace_id == ws, Chunk.strategy == "recursive", Document.status == "ready")
    )
    since = datetime.now(UTC) - timedelta(days=7)
    answers = session.scalars(
        select(Message.metadata_)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.workspace_id == ws,
            Message.role == "assistant",
            Message.created_at >= since,
        )
        .order_by(Message.created_at.desc())
    ).all()
    latencies = [float(v) for m in answers if isinstance(v := m.get("latency_ms"), int | float)]
    sql_count = session.scalar(
        select(func.count())
        .select_from(SqlQueryLog)
        .where(SqlQueryLog.workspace_id == ws, SqlQueryLog.created_at >= since)
    )
    run = session.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.workspace_id == ws, EvaluationRun.status == "succeeded")
        .order_by(EvaluationRun.completed_at.desc().nullslast())
        .limit(1)
    )
    latest = None
    if run is not None:
        agg = run.aggregate_metrics
        latest = LatestRun(
            id=str(run.id),
            label=run.label,
            status=run.status,
            recall_at_k=agg.get("recall_at_k"),
            mrr=agg.get("mrr"),
            cases=run.total,
            created_at=run.created_at,
        )
    processing = sum(counts.get(s, 0) for s in ("queued", "extracting", "chunking", "embedding"))
    return SummaryOut(
        documents=sum(counts.values()),
        documents_ready=counts.get("ready", 0),
        documents_processing=processing,
        documents_failed=counts.get("failed", 0),
        chunks=chunks or 0,
        questions_7d=len(answers),
        abstained_7d=sum(1 for m in answers if m.get("abstained") is True),
        answer_latency_p50_ms=round(statistics.median(latencies), 1) if latencies else None,
        sql_questions_7d=sql_count or 0,
        latest_evaluation=latest,
    )
