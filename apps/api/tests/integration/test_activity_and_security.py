"""M7: audit trail, activity views, and workspace isolation across every resource endpoint."""

import json
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Workspace
from app.modules.documents.extraction import Extraction, Limits, extract
from app.modules.documents.storage import FileStorage
from app.modules.models.embedding_stage import attach_embedding
from app.workers.ingestion import Pipeline, attach_evaluations, run
from tests.fake_ollama import FakeOllama
from tests.files import PDF_MIME, text_pdf_bytes

pytestmark = pytest.mark.integration

SECRET_QUESTION = "What is the hotel cap per night for project Bluebird?"


def in_process(path: Path, file_type: str, limits: Limits, _t: float) -> Extraction:
    return extract(path, file_type, limits)


@pytest.fixture
def pipeline(db_engine: Engine, storage_root: Path, fake_ollama: FakeOllama) -> Pipeline:
    p = Pipeline(
        session_factory=sessionmaker(bind=db_engine, expire_on_commit=False),
        storage=FileStorage(storage_root),
        settings=get_settings(),
        extractor=in_process,
    )
    attach_embedding(p)
    attach_evaluations(p)
    return p


@pytest.fixture
def populated(db_client: TestClient, pipeline: Pipeline, fake_ollama: FakeOllama) -> dict[str, Any]:
    doc = db_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "travel.pdf",
                text_pdf_bytes(["Hotels are capped at 150 EUR per night."]),
                PDF_MIME,
            )
        },
    ).json()
    bad = db_client.post(
        "/api/v1/documents", files={"file": ("scan.pdf", text_pdf_bytes([""]), PDF_MIME)}
    ).json()
    run(pipeline, threading.Event(), once=True)
    fake_ollama.chat_replies.append(
        json.dumps(
            {
                "answer": "Hotels are capped at 150 EUR per night [1].",
                "citations": [1],
                "abstained": False,
            }
        )
    )
    answer = db_client.post(
        "/api/v1/chat/query",
        json={"question": SECRET_QUESTION, "retrieval_config": {"mode": "lexical"}},
    ).json()
    assert "message_id" in answer, answer
    return {"doc": doc["document_id"], "bad": bad["document_id"], "answer": answer}


def test_actions_are_audited_with_request_ids_and_no_content(
    db_client: TestClient, populated: dict[str, Any], db_engine: Engine
) -> None:
    db_client.post(f"/api/v1/documents/{populated['bad']}/retry")
    db_client.delete(f"/api/v1/documents/{populated['doc']}")
    events = db_client.get("/api/v1/activity/events").json()
    actions = [e["action"] for e in events["items"]]
    for expected in (
        "document.created",
        "ingestion.succeeded",
        "ingestion.failed",
        "chat.answered",
        "document.retry",
        "document.deleted",
    ):
        assert expected in actions, actions
    user_events = [e for e in events["items"] if e["actor"] == "local-user"]
    assert all(e["request_id"] for e in user_events)
    worker = next(e for e in events["items"] if e["action"] == "ingestion.failed")
    assert worker["actor"] == "worker"
    assert worker["metadata"]["error_code"] == "no_text_layer"
    with db_engine.connect() as conn:
        dump = json.dumps(
            conn.execute(text("SELECT metadata_safe FROM audit_events")).scalars().all()
        )
    assert "Bluebird" not in dump and "150 EUR" not in dump  # never question or answer text

    chat_only = db_client.get("/api/v1/activity/events", params={"category": "chat"}).json()
    assert {e["action"] for e in chat_only["items"]} == {"chat.answered"}


def test_jobs_and_summary(db_client: TestClient, populated: dict[str, Any]) -> None:
    jobs = db_client.get("/api/v1/activity/jobs").json()
    assert {j["status"] for j in jobs} == {"succeeded", "failed"}
    failed = db_client.get("/api/v1/activity/jobs", params={"status": "failed"}).json()
    assert failed[0]["document_name"] == "scan.pdf"
    assert failed[0]["error_code"] == "no_text_layer"
    summary = db_client.get("/api/v1/activity/summary").json()
    assert summary["documents"] == 2
    assert summary["documents_ready"] == 1
    assert summary["documents_failed"] == 1
    assert summary["chunks"] >= 1
    assert summary["questions_7d"] == 1
    assert summary["answer_latency_p50_ms"] is not None
    assert summary["latest_evaluation"] is None


def test_every_resource_is_invisible_from_another_workspace(
    db_client: TestClient, populated: dict[str, Any], db_engine: Engine
) -> None:
    """TRD §11 cross-workspace leakage: move all content to another workspace, then probe."""
    cid = populated["answer"]["conversation_id"]
    mid = populated["answer"]["message_id"]
    doc = populated["bad"]
    with Session(db_engine) as s:
        other = Workspace(id=uuid.uuid4(), name="Other")
        s.add(other)
        s.flush()
        for table in (
            "documents",
            "chunks",
            "chunk_embeddings",
            "document_sections",
            "conversations",
            "audit_events",
        ):
            s.execute(text(f"UPDATE {table} SET workspace_id = :w"), {"w": other.id})  # noqa: S608
        s.commit()

    not_found = [
        f"/api/v1/documents/{doc}",
        f"/api/v1/documents/{doc}/chunks",
        f"/api/v1/documents/{doc}/extraction",
        f"/api/v1/conversations/{cid}",
    ]
    for url in not_found:
        assert db_client.get(url).status_code == 404, url
    assert db_client.post(f"/api/v1/documents/{doc}/retry").status_code == 404
    assert (
        db_client.put(f"/api/v1/messages/{mid}/feedback", json={"rating": "helpful"}).status_code
        == 404
    )
    assert db_client.get("/api/v1/documents").json()["total"] == 0
    assert db_client.get("/api/v1/conversations").json()["total"] == 0
    assert db_client.get("/api/v1/search", params={"q": "hotel"}).json()["hits"] == []
    assert db_client.get("/api/v1/activity/events").json()["total"] == 0
    assert db_client.get("/api/v1/activity/jobs").json() == []
    assert db_client.get("/api/v1/activity/summary").json()["documents"] == 0
    # Deleting a foreign document is a no-op (idempotent 204) and must not remove it.
    assert db_client.delete(f"/api/v1/documents/{doc}").status_code == 204
    with Session(db_engine) as s:
        assert s.execute(text("SELECT count(*) FROM documents")).scalar() == 2


def test_errors_never_leak_internals(db_client: TestClient, fake_ollama: FakeOllama) -> None:
    fake_ollama.down = True
    r = db_client.get("/api/v1/settings/models")
    body = r.text
    assert "Traceback" not in body and "httpx" not in body
    r = db_client.get("/api/v1/documents/not-a-uuid")
    assert r.status_code == 422
    assert set(r.json()["error"]) >= {"code", "message", "request_id"}
