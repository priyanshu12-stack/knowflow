"""M4 exit: a user asks a question and receives a grounded answer with a clickable citation."""

import json
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Message, MessageFeedback, Workspace
from app.modules.documents.extraction import Extraction, Limits, extract
from app.modules.documents.storage import FileStorage
from app.modules.models.embedding_stage import attach_embedding
from app.modules.rag import service as rag_service
from app.workers.ingestion import Pipeline, run
from tests.fake_ollama import FakeOllama
from tests.files import PDF_MIME, text_pdf_bytes

pytestmark = pytest.mark.integration

PAGES = [
    "Travel Policy\nAll travel must be booked through the TravelDesk portal.",
    "Reimbursement\nHotels are capped at 150 EUR per night.\nMeal allowance is 40 EUR per day.",
    "Approvals\nTrips over 2000 EUR need director approval.",
]


def in_process(path: Path, file_type: str, limits: Limits, _t: float) -> Extraction:
    return extract(path, file_type, limits)


@pytest.fixture
def indexed(
    db_client: TestClient, db_engine: Engine, storage_root: Path, fake_ollama: FakeOllama
) -> str:
    r = db_client.post(
        "/api/v1/documents", files={"file": ("travel.pdf", text_pdf_bytes(PAGES), PDF_MIME)}
    )
    assert r.status_code == 202
    pipeline = Pipeline(
        session_factory=sessionmaker(bind=db_engine, expire_on_commit=False),
        storage=FileStorage(storage_root),
        settings=get_settings(),
        extractor=in_process,
    )
    attach_embedding(pipeline)
    run(pipeline, threading.Event(), once=True)
    return str(r.json()["document_id"])


def reply(fake: FakeOllama, answer: str, citations: list[int], abstained: bool = False) -> None:
    fake.chat_replies.append(
        json.dumps(
            {"answer": answer, "citations": citations, "abstained": abstained, "missing": None}
        )
    )


def ask(client: TestClient, question: str, **extra: Any) -> Any:
    body: dict[str, Any] = {"question": question, **extra}
    return client.post("/api/v1/chat/query", json=body)


def test_grounded_answer_with_citation_to_the_right_page(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    reply(fake_ollama, "Hotels are capped at 150 EUR per night [1].", [1])
    r = ask(db_client, "What is the hotel cap per night?", retrieval_config={"mode": "lexical"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["abstained"] is False
    assert body["answer"] == "Hotels are capped at 150 EUR per night [1]."
    (citation,) = body["citations"]
    assert citation["document_id"] == indexed
    assert citation["page_start"] == 2
    assert "150 EUR" in citation["excerpt"]
    assert body["retrieval"]["mode"] == "lexical"
    assert body["prompt_version"] == "rag-answer-v2"
    assert body["request_id"]

    # The evidence sent to the model is delimited and numbered.
    chat_request = next(b for p, b in reversed(fake_ollama.requests) if p == "/api/chat")
    user = chat_request["messages"][1]["content"]
    assert '<source id="1" document="travel.pdf" location="page 2">' in user
    assert chat_request["format"]["required"] == ["answer", "citations", "abstained"]
    assert chat_request["options"]["temperature"] == 0.1


def test_dense_mode_works_and_history_is_persisted(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    reply(fake_ollama, "Trips over 2000 EUR need director approval [1].", [1])
    first = ask(db_client, "who approves trips over 2000 EUR").json()
    assert first["retrieval"]["mode"] == "dense"
    assert first["citations"]
    cid = first["conversation_id"]

    reply(fake_ollama, "Meals are 40 EUR per day [1].", [1])
    second = ask(db_client, "meal allowance per day", conversation_id=cid).json()
    assert second["conversation_id"] == cid

    listing = db_client.get("/api/v1/conversations").json()
    assert listing["total"] == 1
    assert listing["items"][0]["message_count"] == 4
    assert listing["items"][0]["title"] == "who approves trips over 2000 EUR"

    detail = db_client.get(f"/api/v1/conversations/{cid}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["citations"][0]["page_start"] == 3
    assert assistant["metadata"]["retrieval"]["candidate_ranks"]
    # The trace stores ids, counts and timings, never the prompt or the evidence text.
    stored = json.dumps(assistant["metadata"])
    assert "untrusted" not in stored
    assert "Hotels are capped" not in stored


def test_no_matching_evidence_abstains_without_generation(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    before = sum(1 for p, _ in fake_ollama.requests if p == "/api/chat")
    r = ask(db_client, "quantum chromodynamics", retrieval_config={"mode": "lexical"}).json()
    assert r["abstained"] is True
    assert r["abstain_reason"] == "no_sources"
    assert r["citations"] == []
    assert sum(1 for p, _ in fake_ollama.requests if p == "/api/chat") == before


def test_uncited_model_answer_becomes_an_abstention(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    reply(fake_ollama, "Hotels are probably 300 EUR.", [])
    r = ask(db_client, "hotel cap", retrieval_config={"mode": "lexical"}).json()
    assert r["abstained"] is True
    assert r["abstain_reason"] == "unsupported"
    assert "300" not in r["answer"]


def test_document_scope_is_validated_and_applied(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    bad = ask(db_client, "hotel", document_ids=[str(uuid.uuid4())])
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_document_scope"
    reply(fake_ollama, "Hotels are capped at 150 EUR [1].", [1])
    ok = ask(db_client, "hotel cap", document_ids=[indexed], retrieval_config={"mode": "lexical"})
    assert ok.status_code == 200
    assert ok.json()["citations"][0]["document_id"] == indexed


def test_model_failure_is_a_safe_503(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama
) -> None:
    fake_ollama.chat_replies.append("not json at all")
    r = ask(db_client, "hotel cap", retrieval_config={"mode": "lexical"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "model_invalid_output"
    assert db_client.get("/api/v1/conversations").json()["total"] == 0  # nothing half-saved


def test_concurrent_generation_is_capped(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = threading.BoundedSemaphore(1)
    monkeypatch.setattr(rag_service, "_generation_gate", lambda _settings: gate)
    settings = get_settings().model_copy(update={"generation_queue_wait_seconds": 0})
    app = db_client.app
    app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]
    gate.acquire()  # another answer is in progress
    try:
        r = ask(db_client, "hotel cap", retrieval_config={"mode": "lexical"})
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "generation_busy"
    finally:
        gate.release()
        del app.dependency_overrides[get_settings]  # type: ignore[attr-defined]


def test_conversations_rename_delete_and_feedback(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama, db_engine: Engine
) -> None:
    reply(fake_ollama, "Hotels are capped at 150 EUR [1].", [1])
    answer = ask(db_client, "hotel cap", retrieval_config={"mode": "lexical"}).json()
    cid, mid = answer["conversation_id"], answer["message_id"]

    renamed = db_client.patch(f"/api/v1/conversations/{cid}", json={"title": "  Hotels  "}).json()
    assert renamed["title"] == "Hotels"
    assert db_client.patch(f"/api/v1/conversations/{cid}", json={"title": "  "}).status_code == 422

    assert (
        db_client.put(
            f"/api/v1/messages/{mid}/feedback",
            json={"rating": "not_helpful", "reason": "too short"},
        ).status_code
        == 204
    )
    db_client.put(f"/api/v1/messages/{mid}/feedback", json={"rating": "helpful"})  # upsert
    detail = db_client.get(f"/api/v1/conversations/{cid}").json()
    assert detail["messages"][1]["feedback"] == {"rating": "helpful", "reason": None}
    user_mid = detail["messages"][0]["id"]
    assert (
        db_client.put(
            f"/api/v1/messages/{user_mid}/feedback", json={"rating": "helpful"}
        ).status_code
        == 404
    )  # only answers take feedback

    assert db_client.delete(f"/api/v1/conversations/{cid}").status_code == 204
    assert db_client.delete(f"/api/v1/conversations/{cid}").status_code == 204  # idempotent
    assert db_client.get(f"/api/v1/conversations/{cid}").status_code == 404
    with Session(db_engine) as s:
        assert s.scalar(select(func.count()).select_from(Message)) == 0
        assert s.scalar(select(func.count()).select_from(MessageFeedback)) == 0


def test_conversations_are_workspace_scoped(
    db_client: TestClient, indexed: str, fake_ollama: FakeOllama, db_engine: Engine
) -> None:
    reply(fake_ollama, "Hotels are capped at 150 EUR [1].", [1])
    cid = ask(db_client, "hotel cap", retrieval_config={"mode": "lexical"}).json()[
        "conversation_id"
    ]
    with Session(db_engine) as s:
        other = Workspace(id=uuid.uuid4(), name="Other")
        s.add(other)
        s.flush()
        s.execute(text("UPDATE conversations SET workspace_id = :w"), {"w": other.id})
        s.commit()
    assert db_client.get(f"/api/v1/conversations/{cid}").status_code == 404
    assert db_client.get("/api/v1/conversations").json()["total"] == 0
    assert ask(db_client, "x", conversation_id=cid).status_code == 404


def test_question_validation(db_client: TestClient, fake_ollama: FakeOllama) -> None:
    assert ask(db_client, "   ").status_code == 422
    assert ask(db_client, "x" * 2001).status_code == 422
    assert ask(db_client, "ok", retrieval_config={"top_k": 99}).status_code == 422
