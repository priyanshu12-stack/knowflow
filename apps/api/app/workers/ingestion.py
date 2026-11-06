"""PostgreSQL-backed ingestion worker (TRD §3 "Background jobs", §6.1, §12).

One process claims queued jobs with `FOR UPDATE SKIP LOCKED`, so several workers would be safe
but one is enough for v1. Each job moves the document through
queued → extracting → chunking → (embedding) → ready | failed.

Reliability rules:
- Status changes are committed as they happen so the UI shows real progress.
- Sections, chunks and the `ready` status are written in one transaction: a document is never
  ready with partial chunks, and a failed attempt leaves no partial rows behind.
- Re-running a job replaces earlier sections/chunks, so retries are idempotent.
- A running job refreshes `heartbeat_at`. On start and on every poll, jobs whose heartbeat is
  older than `job_stale_seconds` (the worker crashed or was killed) are re-queued, or failed once
  they have used all attempts.
- Retryable failures (timeouts, model unavailable) back off exponentially; bad input fails at once.

Run: ./scripts/dev.ps1 worker   (or: python -m app.workers.ingestion)
"""

import logging
import os
import signal
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models import Chunk, Document, DocumentSection, IngestionJob, WorkerHeartbeat
from app.modules.documents import chunking
from app.modules.documents.extraction import (
    Extraction,
    ExtractionError,
    Limits,
    extract_with_timeout,
)
from app.modules.documents.status import JobStage
from app.modules.documents.storage import FileStorage

logger = logging.getLogger(__name__)

WORKER_NAME = "ingestion"


class IngestionError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class EmbeddedChunks:
    version_id: uuid.UUID
    vectors: dict[tuple[str, int], list[float]]  # (strategy, chunk_index) -> vector


Extractor = Callable[[Path, str, Limits, float], Extraction]
# (session, chunk ids by (strategy, index), vectors, workspace_id) -> None
# Embeds chunk texts (M3): (session factory, chunks, job id) -> vectors in one embedding version.
ChunkEmbedder = Callable[[sessionmaker[Session], list[chunking.Chunk], uuid.UUID], "EmbeddedChunks"]
VectorWriter = Callable[
    [Session, dict[tuple[str, int], uuid.UUID], "EmbeddedChunks", uuid.UUID], None
]


@dataclass
class Pipeline:
    session_factory: sessionmaker[Session]
    storage: FileStorage
    settings: Settings
    extractor: Extractor = extract_with_timeout
    embedder: ChunkEmbedder | None = None
    # Persists vectors inside the final transaction (M3); None keeps M2 behaviour.
    store_vectors: VectorWriter | None = None

    @property
    def chunking_config(self) -> chunking.ChunkingConfig:
        return chunking.ChunkingConfig(
            size=self.settings.chunk_size_chars, overlap=self.settings.chunk_overlap_chars
        )


def _now() -> datetime:
    return datetime.now(UTC)


# --- Queue operations ---


def recover_stale_jobs(session: Session, settings: Settings) -> int:
    """Re-queue (or fail) running jobs whose worker stopped heart-beating."""
    cutoff = _now() - timedelta(seconds=settings.job_stale_seconds)
    stale = session.scalars(
        select(IngestionJob)
        .where(IngestionJob.status == "running", IngestionJob.heartbeat_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    for job in stale:
        document = session.get(Document, job.document_id)
        if job.attempts >= settings.job_max_attempts:
            job.status, job.completed_at = "failed", _now()
            job.error_code = "worker_interrupted"
            job.error_message_safe = (
                "Processing was interrupted repeatedly (the worker stopped). Retry the document."
            )
            if document:
                document.status = "failed"
        else:
            job.status, job.stage, job.retry_after = "queued", None, None
            if document:
                document.status = "queued"
        logger.warning("stale_job_recovered", extra={"job_id": str(job.id), "to": job.status})
    session.commit()
    return len(stale)


def claim_next_job(session: Session) -> uuid.UUID | None:
    now = _now()
    job = session.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.status == "queued",
            (IngestionJob.retry_after.is_(None)) | (IngestionJob.retry_after <= now),
        )
        .order_by(IngestionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        session.rollback()
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = job.heartbeat_at = now
    job.retry_after = None
    job.error_code = job.error_message_safe = None
    session.commit()
    return job.id


def beat(session: Session) -> None:
    """Record that this worker process is alive (shown in /health/ready)."""
    stmt = insert(WorkerHeartbeat).values(name=WORKER_NAME, pid=os.getpid(), last_seen_at=_now())
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[WorkerHeartbeat.name],
            set_={"pid": stmt.excluded.pid, "last_seen_at": stmt.excluded.last_seen_at},
        )
    )
    session.commit()


# --- Job processing ---


def _set_stage(pipeline: Pipeline, job_id: uuid.UUID, stage: JobStage) -> None:
    with pipeline.session_factory() as session:
        job = session.get(IngestionJob, job_id)
        if job is None:
            raise _GoneError
        job.stage, job.heartbeat_at = stage, _now()
        session.execute(update(Document).where(Document.id == job.document_id).values(status=stage))
        session.commit()


class _GoneError(Exception):
    """The document (and its job) was deleted while processing; stop quietly."""


def _fail(pipeline: Pipeline, job_id: uuid.UUID, error: IngestionError) -> None:
    settings = pipeline.settings
    with pipeline.session_factory() as session:
        job = session.get(IngestionJob, job_id)
        if job is None:
            return
        document = session.get(Document, job.document_id)
        job.error_code, job.error_message_safe = error.code, error.message
        if error.retryable and job.attempts < settings.job_max_attempts:
            delay = settings.job_retry_base_seconds * 2 ** (job.attempts - 1)
            job.status, job.stage = "queued", None
            job.retry_after = _now() + timedelta(seconds=delay)
            if document:
                document.status = "queued"
        else:
            job.status, job.completed_at = "failed", _now()
            if document:
                document.status = "failed"
        session.commit()
        logger.warning(
            "ingestion_failed",
            extra={
                "job_id": str(job_id),
                "error_code": error.code,
                "attempt": job.attempts,
                "next_status": job.status,
            },
        )


def process_job(pipeline: Pipeline, job_id: uuid.UUID) -> None:
    started = _now()
    with pipeline.session_factory() as session:
        job = session.get(IngestionJob, job_id)
        document = session.get(Document, job.document_id) if job else None
        if job is None or document is None:
            return
        doc_id, workspace_id = document.id, document.workspace_id
        file_type, key = document.file_type, document.storage_key
    try:
        _set_stage(pipeline, job_id, "extracting")
        path = pipeline.storage.path_for(key)
        if not path.is_file():
            raise IngestionError(
                "file_missing", "The stored file is missing. Upload it again.", retryable=False
            )
        settings = pipeline.settings
        try:
            extraction = pipeline.extractor(
                path,
                file_type,
                Limits(max_pages=settings.max_pdf_pages, max_chars=settings.max_extracted_chars),
                settings.extraction_timeout_seconds,
            )
        except ExtractionError as exc:
            retryable = exc.retryable or exc.code == "extraction_timeout"
            raise IngestionError(exc.code, exc.message, retryable=retryable) from exc

        _set_stage(pipeline, job_id, "chunking")
        cfg = pipeline.chunking_config
        chunks = [c for s in chunking.STRATEGIES for c in chunking.chunk(extraction.units, s, cfg)]

        embedded: EmbeddedChunks | None = None
        if pipeline.embedder is not None:
            _set_stage(pipeline, job_id, "embedding")
            embedded = pipeline.embedder(pipeline.session_factory, chunks, job_id)

        _complete(pipeline, job_id, doc_id, workspace_id, extraction, chunks, embedded)
    except _GoneError:
        logger.info("ingestion_document_deleted", extra={"job_id": str(job_id)})
        return
    except IngestionError as exc:
        _fail(pipeline, job_id, exc)
        return
    except Exception:
        logger.exception("ingestion_crashed", extra={"job_id": str(job_id)})
        _fail(
            pipeline,
            job_id,
            IngestionError(
                "ingestion_failed",
                "Processing failed unexpectedly. Retry, or check the worker log.",
                retryable=True,
            ),
        )
        return
    logger.info(
        "ingestion_succeeded",
        extra={
            "job_id": str(job_id),
            "document_id": str(doc_id),
            "chunks": len(chunks),
            "duration_ms": round((_now() - started).total_seconds() * 1000),
        },
    )


def _complete(
    pipeline: Pipeline,
    job_id: uuid.UUID,
    doc_id: uuid.UUID,
    workspace_id: uuid.UUID,
    extraction: Extraction,
    chunks: list[chunking.Chunk],
    embedded: EmbeddedChunks | None,
) -> None:
    with pipeline.session_factory() as session:
        job = session.get(IngestionJob, job_id, with_for_update=True)
        document = session.get(Document, doc_id, with_for_update=True)
        if job is None or document is None:
            raise _GoneError
        session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
        session.execute(delete(DocumentSection).where(DocumentSection.document_id == doc_id))
        session.add_all(
            DocumentSection(
                document_id=doc_id,
                workspace_id=workspace_id,
                ordinal=i,
                page_number=u.page,
                section_path=chunking.SECTION_SEPARATOR.join(u.section_path) or None,
                text=u.text,
            )
            for i, u in enumerate(extraction.units)
        )
        ids: dict[tuple[str, int], uuid.UUID] = {}
        for c in chunks:
            chunk_id = uuid.uuid4()
            ids[(c.strategy, c.index)] = chunk_id
            session.add(
                Chunk(
                    id=chunk_id,
                    document_id=doc_id,
                    workspace_id=workspace_id,
                    strategy=c.strategy,
                    chunk_index=c.index,
                    text=c.text,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    section_path=c.section_path,
                    char_count=c.char_count,
                    token_count=c.token_count,
                    content_hash=c.content_hash,
                )
            )
        session.flush()
        if embedded is not None and pipeline.store_vectors is not None:
            pipeline.store_vectors(session, ids, embedded, workspace_id)
        document.status = "ready"
        document.page_count = extraction.page_count
        document.extracted_char_count = extraction.char_count
        document.citation_granularity = extraction.granularity
        job.status, job.stage, job.completed_at = "succeeded", None, _now()
        session.commit()


# --- Process loop ---


def run(pipeline: Pipeline, stop: threading.Event, *, once: bool = False) -> int:
    """Process jobs until `stop` is set (or the queue is empty when `once`). Returns jobs run."""
    processed = 0
    with pipeline.session_factory() as session:
        recover_stale_jobs(session, pipeline.settings)
    while not stop.is_set():
        with pipeline.session_factory() as session:
            beat(session)
            recover_stale_jobs(session, pipeline.settings)
            job_id = claim_next_job(session)
        if job_id is None:
            if once:
                break
            stop.wait(pipeline.settings.worker_poll_seconds)
            continue
        process_job(pipeline, job_id)
        processed += 1
    return processed


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    from app.db.session import get_engine

    settings = settings or get_settings()
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    pipeline = Pipeline(
        session_factory=factory, storage=FileStorage(settings.storage_root), settings=settings
    )
    from app.modules.models.embedding_stage import attach_embedding

    attach_embedding(pipeline)
    return pipeline


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def _stop(signum: int, _frame: object) -> None:
        logger.info("worker_stopping", extra={"signal": signum})
        stop.set()  # finish the current job, then exit (graceful shutdown, TRD §12)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    logger.info("worker_started", extra={"pid": os.getpid()})
    run(build_pipeline(settings), stop)
    logger.info("worker_stopped")


if __name__ == "__main__":
    main()
