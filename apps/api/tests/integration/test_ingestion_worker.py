"""M2 exit: an uploaded file becomes searchable chunks; restart and failure states are tested."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Chunk, Document, DocumentSection, IngestionJob
from app.modules.documents.extraction import Extraction, ExtractionError, Limits, extract
from app.modules.documents.storage import FileStorage
from app.workers.ingestion import Pipeline, claim_next_job, process_job, recover_stale_jobs, run
from tests.files import DOCX_MIME, PDF_MIME, real_docx_bytes, text_pdf_bytes

pytestmark = pytest.mark.integration

HANDBOOK_MD = (
    "# Handbook\nWelcome.\n\n## Leave\nEmployees receive 24 days of paid annual leave.\n\n"
    "## Expenses\nSubmit receipts within 30 days using form EXP-7.\n"
)


def in_process(path: Path, file_type: str, limits: Limits, _timeout: float) -> Extraction:
    return extract(path, file_type, limits)


@pytest.fixture
def pipeline(db_engine: Engine, storage_root: Path) -> Pipeline:
    settings = get_settings().model_copy(
        update={"job_retry_base_seconds": 0, "chunk_size_chars": 300, "chunk_overlap_chars": 50}
    )
    return Pipeline(
        session_factory=sessionmaker(bind=db_engine, expire_on_commit=False),
        storage=FileStorage(storage_root),
        settings=settings,
        extractor=in_process,
    )


def upload(client: TestClient, name: str, data: bytes, mime: str = "text/markdown") -> Any:
    response = client.post("/api/v1/documents", files={"file": (name, data, mime)})
    assert response.status_code == 202, response.text
    return response.json()


def drain(pipeline: Pipeline) -> int:
    return run(pipeline, threading.Event(), once=True)


def test_markdown_upload_becomes_searchable_chunks(
    db_client: TestClient, pipeline: Pipeline, db_session: Session
) -> None:
    doc = upload(db_client, "handbook.md", HANDBOOK_MD.encode())
    assert drain(pipeline) == 1

    detail = db_client.get(f"/api/v1/documents/{doc['document_id']}").json()
    assert detail["status"] == "ready"
    assert detail["latest_job"]["status"] == "succeeded"
    assert detail["citation_granularity"] == "section"
    assert detail["chunk_count"] >= 2

    chunks = db_client.get(f"/api/v1/documents/{doc['document_id']}/chunks").json()
    assert chunks["total"] == detail["chunk_count"]
    assert {c["section_path"] for c in chunks["items"]} >= {"Handbook > Leave"}
    fixed = db_client.get(
        f"/api/v1/documents/{doc['document_id']}/chunks", params={"strategy": "fixed"}
    ).json()
    assert fixed["total"] >= 1

    preview = db_client.get(f"/api/v1/documents/{doc['document_id']}/extraction").json()
    assert preview["total_sections"] == 3

    hits = db_client.get("/api/v1/search", params={"q": "receipts EXP-7"}).json()["hits"]
    assert hits
    assert hits[0]["document_name"] == "handbook.md"
    assert "EXP-7" in hits[0]["text"]
    assert hits[0]["section_path"] == "Handbook > Expenses"


def test_pdf_and_docx_keep_pages_and_headings(db_client: TestClient, pipeline: Pipeline) -> None:
    pdf = upload(
        db_client, "p.pdf", text_pdf_bytes(["Intro page", "Refund window is 45 days"]), PDF_MIME
    )
    docx = upload(db_client, "h.docx", real_docx_bytes(), DOCX_MIME)
    assert drain(pipeline) == 2

    pdf_detail = db_client.get(f"/api/v1/documents/{pdf['document_id']}").json()
    assert pdf_detail["status"] == "ready"
    assert pdf_detail["page_count"] == 2
    hit = db_client.get("/api/v1/search", params={"q": "refund window"}).json()["hits"][0]
    assert hit["page_start"] == 2

    docx_hit = db_client.get("/api/v1/search", params={"q": "paid annual leave"}).json()["hits"]
    assert docx_hit[0]["document_id"] == docx["document_id"]
    assert docx_hit[0]["section_path"] == "Employee Handbook > Leave"


def test_bad_input_fails_once_with_a_plain_error_and_can_be_retried(
    db_client: TestClient, pipeline: Pipeline
) -> None:
    doc = upload(db_client, "scan.pdf", text_pdf_bytes(["", ""]), PDF_MIME)
    drain(pipeline)
    detail = db_client.get(f"/api/v1/documents/{doc['document_id']}").json()
    assert detail["status"] == "failed"
    assert detail["latest_job"]["attempts"] == 1  # not retried automatically
    assert detail["last_error"]["code"] == "no_text_layer"
    assert detail["chunk_count"] is None

    retried = db_client.post(f"/api/v1/documents/{doc['document_id']}/retry")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    # idempotent: a second retry reuses the queued job
    db_client.post(f"/api/v1/documents/{doc['document_id']}/retry")
    assert drain(pipeline) == 1


def test_retryable_failure_backs_off_then_fails_after_max_attempts(
    db_client: TestClient, pipeline: Pipeline, db_session: Session
) -> None:
    calls = 0

    def flaky(path: Path, file_type: str, limits: Limits, timeout: float) -> Extraction:
        nonlocal calls
        calls += 1
        raise ExtractionError("extraction_timeout", "Took too long.")

    pipeline.extractor = flaky
    doc = upload(db_client, "slow.md", b"# Slow\nbody")
    drain(pipeline)
    assert calls == pipeline.settings.job_max_attempts
    job = db_session.scalar(
        select(IngestionJob).where(IngestionJob.document_id == uuid.UUID(doc["document_id"]))
    )
    assert job is not None
    assert job.status == "failed"
    assert job.error_code == "extraction_timeout"


def test_retry_after_is_respected(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine
) -> None:
    pipeline.settings = pipeline.settings.model_copy(update={"job_retry_base_seconds": 600})
    pipeline.extractor = lambda *a: (_ for _ in ()).throw(
        ExtractionError("extraction_timeout", "x")
    )
    upload(db_client, "later.md", b"# Later\nbody")
    assert drain(pipeline) == 1  # one attempt, then the job waits for retry_after
    with Session(db_engine) as s:
        job = s.scalars(select(IngestionJob)).one()
        assert job.status == "queued"
        assert job.retry_after is not None
        assert claim_next_job(s) is None


def test_stale_running_job_is_recovered_after_a_worker_crash(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine
) -> None:
    doc = upload(db_client, "crash.md", HANDBOOK_MD.encode())
    with Session(db_engine, expire_on_commit=False) as s:
        job_id = claim_next_job(s)
        assert job_id is not None
        # Simulate a worker that died mid-extraction long ago.
        job = s.get(IngestionJob, job_id)
        assert job is not None
        job.stage = "extracting"
        job.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
        s.get(Document, job.document_id).status = "extracting"  # type: ignore[union-attr]
        s.commit()
        assert recover_stale_jobs(s, pipeline.settings) == 1
        s.refresh(job)
        assert job.status == "queued"

    assert drain(pipeline) == 1  # a restarted worker picks it up
    assert db_client.get(f"/api/v1/documents/{doc['document_id']}").json()["status"] == "ready"


def test_reindex_replaces_chunks_instead_of_duplicating(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine
) -> None:
    doc = upload(db_client, "h.md", HANDBOOK_MD.encode())
    drain(pipeline)
    with Session(db_engine) as s:
        before = s.scalar(select(func.count()).select_from(Chunk))
        sections = s.scalar(select(func.count()).select_from(DocumentSection))
    db_client.post(f"/api/v1/documents/{doc['document_id']}/retry")
    drain(pipeline)
    with Session(db_engine) as s:
        assert s.scalar(select(func.count()).select_from(Chunk)) == before
        assert s.scalar(select(func.count()).select_from(DocumentSection)) == sections


def test_document_deleted_mid_job_is_ignored(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine
) -> None:
    doc = upload(db_client, "gone.md", HANDBOOK_MD.encode())
    with Session(db_engine) as s:
        job_id = claim_next_job(s)
    assert job_id is not None
    assert db_client.delete(f"/api/v1/documents/{doc['document_id']}").status_code == 204
    process_job(pipeline, job_id)  # must not raise
    with Session(db_engine) as s:
        assert s.scalar(select(func.count()).select_from(Chunk)) == 0


def test_missing_file_fails_without_retry(
    db_client: TestClient, pipeline: Pipeline, storage_root: Path
) -> None:
    doc = upload(db_client, "lost.md", HANDBOOK_MD.encode())
    for f in storage_root.rglob("*"):
        if f.is_file() and ".incoming" not in f.parts:
            f.unlink()
    drain(pipeline)
    detail = db_client.get(f"/api/v1/documents/{doc['document_id']}").json()
    assert detail["status"] == "failed"
    assert detail["last_error"]["code"] == "file_missing"


def test_search_is_workspace_scoped_and_only_sees_ready_documents(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine
) -> None:
    upload(db_client, "h.md", HANDBOOK_MD.encode())
    assert db_client.get("/api/v1/search", params={"q": "receipts"}).json()["hits"] == []
    drain(pipeline)
    assert db_client.get("/api/v1/search", params={"q": "receipts"}).json()["hits"]
    # Move the chunks to another workspace: they must disappear from this workspace's search.
    with Session(db_engine) as s:
        from app.db.models import Workspace

        other = Workspace(id=uuid.uuid4(), name="Other")
        s.add(other)
        s.flush()
        s.execute(Chunk.__table__.update().values(workspace_id=other.id))
        s.commit()
    assert db_client.get("/api/v1/search", params={"q": "receipts"}).json()["hits"] == []


def test_worker_readiness_reflects_heartbeat(db_client: TestClient, pipeline: Pipeline) -> None:
    from app.core.readiness import check_worker

    engine = pipeline.session_factory.kw["bind"]
    assert check_worker(engine, pipeline.settings)[0].state == "missing"
    drain(pipeline)
    check = check_worker(engine, pipeline.settings)[0]
    assert check.state == "ok"
    assert "pid" in check.detail
