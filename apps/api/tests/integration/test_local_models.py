"""M3 exit: embeddings are generated locally, stored per embedding version, and a missing model
gives actionable instructions. Ollama is faked here; `test_real_ollama.py` covers the real one."""

import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import ChunkEmbedding, EmbeddingVersion
from app.modules.documents.extraction import Extraction, Limits, extract
from app.modules.documents.storage import FileStorage
from app.modules.models.embedding_stage import attach_embedding
from app.workers.ingestion import Pipeline, run
from tests.fake_ollama import DIM, FakeOllama

pytestmark = pytest.mark.integration

DOC = (
    "# Policies\n\n## Travel\nBook flights through the travel portal; hotels are capped at 150 "
    "euros.\n\n## Security\nLaptops must use full disk encryption and a screen lock.\n"
)


def in_process(path: Path, file_type: str, limits: Limits, _t: float) -> Extraction:
    return extract(path, file_type, limits)


@pytest.fixture
def pipeline(db_engine: Engine, storage_root: Path, fake_ollama: FakeOllama) -> Pipeline:
    settings = get_settings().model_copy(
        update={"job_retry_base_seconds": 0, "embedding_batch_size": 2}
    )
    p = Pipeline(
        session_factory=sessionmaker(bind=db_engine, expire_on_commit=False),
        storage=FileStorage(storage_root),
        settings=settings,
        extractor=in_process,
    )
    attach_embedding(p)
    return p


def upload(client: TestClient, name: str, data: bytes) -> Any:
    r = client.post("/api/v1/documents", files={"file": (name, data, "text/markdown")})
    assert r.status_code == 202, r.text
    return r.json()


def drain(p: Pipeline) -> None:
    run(p, threading.Event(), once=True)


def test_chunks_are_embedded_with_a_probed_version_and_dense_search_works(
    db_client: TestClient, pipeline: Pipeline, db_engine: Engine, fake_ollama: FakeOllama
) -> None:
    doc = upload(db_client, "policies.md", DOC.encode())
    drain(pipeline)
    assert db_client.get(f"/api/v1/documents/{doc['document_id']}").json()["status"] == "ready"

    with Session(db_engine) as s:
        version = s.scalars(select(EmbeddingVersion)).one()
        assert version.is_active
        assert version.dimension == DIM  # measured by the probe, not assumed
        assert version.document_prefix == "search_document: "
        vectors = s.scalar(select(func.count()).select_from(ChunkEmbedding))
        chunks = db_client.get(f"/api/v1/documents/{doc['document_id']}/chunks").json()["total"]
        fixed = db_client.get(
            f"/api/v1/documents/{doc['document_id']}/chunks", params={"strategy": "fixed"}
        ).json()["total"]
        assert vectors == chunks + fixed  # both strategies embedded

    embedded = [b["input"] for path, b in fake_ollama.requests if path == "/api/embed"]
    batches = embedded[1:]  # the first call is the dimension probe
    assert all(len(b) <= 2 for b in batches)
    assert all(t.startswith("search_document: ") for b in batches for t in b)
    assert any("Policies > Security" in t for b in batches for t in b)  # heading context

    hits = db_client.get(
        "/api/v1/search", params={"q": "laptop disk encryption", "mode": "dense"}
    ).json()["hits"]
    assert hits[0]["section_path"] == "Policies > Security"
    query = next(b["input"][0] for p, b in reversed(fake_ollama.requests) if p == "/api/embed")
    assert query.startswith("search_query: ")


def test_missing_embedding_model_keeps_document_queued_with_the_pull_command(
    db_client: TestClient, pipeline: Pipeline, fake_ollama: FakeOllama
) -> None:
    fake_ollama.models = ["qwen3:4b"]
    pipeline.settings = pipeline.settings.model_copy(update={"job_retry_base_seconds": 600})
    doc = upload(db_client, "p.md", DOC.encode())
    drain(pipeline)
    detail = db_client.get(f"/api/v1/documents/{doc['document_id']}").json()
    assert detail["status"] == "queued"  # retried later, once the model is pulled
    assert "ollama pull nomic-embed-text:v1.5" in detail["latest_job"]["error_message_safe"]


def test_ollama_down_fails_after_retries_without_partial_chunks(
    db_client: TestClient, pipeline: Pipeline, fake_ollama: FakeOllama, db_engine: Engine
) -> None:
    fake_ollama.down = True
    doc = upload(db_client, "p.md", DOC.encode())
    drain(pipeline)
    detail = db_client.get(f"/api/v1/documents/{doc['document_id']}").json()
    assert detail["status"] == "failed"
    assert detail["last_error"]["code"] == "ollama_unavailable"
    assert db_client.get(f"/api/v1/documents/{doc['document_id']}/chunks").json()["total"] == 0


def test_dense_search_before_any_embedding_explains_what_to_do(
    db_client: TestClient, fake_ollama: FakeOllama
) -> None:
    r = db_client.get("/api/v1/search", params={"q": "x", "mode": "dense"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_embeddings"


def test_models_settings_lists_runtime_and_installed_models(
    db_client: TestClient, fake_ollama: FakeOllama
) -> None:
    body = db_client.get("/api/v1/settings/models").json()
    assert body["runtime"]["reachable"] is True
    kinds = {m["name"]: m["kind"] for m in body["installed"]}
    assert kinds == {"qwen3:4b": "generation", "nomic-embed-text:v1.5": "embedding"}
    assert body["generation_model"] == "qwen3:4b"
    assert body["active_embedding"] is None
    assert body["reranker"]["enabled"] is False
    assert not any("ollama pull" in c for c in body["setup_commands"])

    fake_ollama.down = True
    down = db_client.get("/api/v1/settings/models").json()
    assert down["runtime"]["reachable"] is False
    assert down["installed"] == []


def test_validate_probes_dimension_and_structured_output(
    db_client: TestClient, fake_ollama: FakeOllama
) -> None:
    ok = db_client.post(
        "/api/v1/settings/models/validate",
        json={"generation_model": "qwen3:4b", "embedding_model": "nomic-embed-text:v1.5"},
    ).json()
    assert ok["ok"] is True
    assert ok["embedding_dimension"] == DIM
    assert {c["name"]: c["state"] for c in ok["checks"]}["generation_model"] == "ok"

    fake_ollama.chat_replies.append('{"wrong": 1}')
    bad = db_client.post(
        "/api/v1/settings/models/validate",
        json={"generation_model": "qwen3:4b", "embedding_model": "missing-embed"},
    ).json()
    states = {c["name"]: c for c in bad["checks"]}
    assert bad["ok"] is False
    assert "ollama pull missing-embed" in states["embedding_model"]["detail"]
    assert states["generation_model"]["state"] == "failed"


def test_model_names_are_validated(db_client: TestClient, fake_ollama: FakeOllama) -> None:
    r = db_client.put(
        "/api/v1/settings/models",
        json={"generation_model": "qwen3:4b; rm -rf /", "embedding_model": "nomic-embed-text:v1.5"},
    )
    assert r.status_code == 422


def test_changing_embedding_model_requires_reindex(
    db_client: TestClient, pipeline: Pipeline, fake_ollama: FakeOllama, db_engine: Engine
) -> None:
    upload(db_client, "p.md", DOC.encode())
    drain(pipeline)
    fake_ollama.models.append("other-embed:latest")

    saved = db_client.put(
        "/api/v1/settings/models",
        json={"generation_model": "qwen3:4b", "embedding_model": "other-embed:latest"},
    ).json()
    assert saved["reembed_required"] is True
    assert saved["settings"]["embedding_model"] == "other-embed:latest"
    assert saved["settings"]["active_embedding"]["model"] == "other-embed:latest"
    assert saved["settings"]["documents_needing_reindex"] == 1
    # Old-space vectors are no longer searched.
    assert (
        db_client.get("/api/v1/search", params={"q": "laptop", "mode": "dense"}).json()["hits"]
        == []
    )

    assert db_client.post("/api/v1/settings/reindex").json() == {"queued": 1}
    drain(pipeline)
    after = db_client.get("/api/v1/settings/models").json()
    assert after["documents_needing_reindex"] == 0
    assert db_client.get("/api/v1/search", params={"q": "laptop", "mode": "dense"}).json()["hits"]
    with Session(db_engine) as s:
        assert s.scalar(select(func.count()).select_from(EmbeddingVersion)) == 2

    health = db_client.get("/api/v1/settings/models").json()
    assert health["embedding_model"] == "other-embed:latest"


def test_saving_an_uninstalled_model_is_rejected(
    db_client: TestClient, fake_ollama: FakeOllama
) -> None:
    r = db_client.put(
        "/api/v1/settings/models",
        json={"generation_model": "qwen3:8b", "embedding_model": "nomic-embed-text:v1.5"},
    )
    assert r.status_code == 422
    assert "qwen3:8b" in r.json()["error"]["message"]
