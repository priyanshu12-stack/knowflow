"""M5 exit: S1-S4 run on the same gold set and produce reproducible metrics (fake models)."""

import csv
import io
import json
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
from app.db.models import EvaluationResult, EvaluationRun
from app.modules.documents.extraction import Extraction, Limits, extract
from app.modules.documents.storage import FileStorage
from app.modules.evaluation import runner
from app.modules.models import reranker as rr
from app.modules.models.embedding_stage import attach_embedding
from app.modules.models.registry import chat_model
from app.workers.ingestion import Pipeline, attach_evaluations, run
from tests.fake_ollama import FakeOllama

pytestmark = pytest.mark.integration


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


def drain(p: Pipeline) -> int:
    return run(p, threading.Event(), once=True)


@pytest.fixture
def sample(db_client: TestClient, pipeline: Pipeline) -> str:
    r = db_client.post("/api/v1/evaluations/sample")
    assert r.status_code == 202, r.text
    assert r.json()["documents_queued"] == 5
    drain(pipeline)
    return str(r.json()["dataset_id"])


def start(client: TestClient, dataset_id: str, **config: Any) -> Any:
    r = client.post("/api/v1/evaluations/runs", json={"dataset_id": dataset_id, "config": config})
    assert r.status_code == 202, r.text
    return r.json()


def test_sample_dataset_is_loaded_idempotently(db_client: TestClient, sample: str) -> None:
    ds = db_client.get(f"/api/v1/evaluations/datasets/{sample}").json()
    assert ds["cases"] == 50
    assert ds["test_cases"] == 12
    assert ds["missing_documents"] == []  # every evidence document is indexed
    again = db_client.post("/api/v1/evaluations/sample").json()
    assert again["dataset_id"] == sample
    assert again["documents_existing"] == 5
    assert again["documents_queued"] == 0


def test_s1_to_s3_run_on_the_same_gold_set(
    db_client: TestClient, pipeline: Pipeline, sample: str
) -> None:
    runs = [start(db_client, sample, preset=p) for p in ("S1", "S2", "S3")]
    assert all(r["status"] == "queued" and r["total"] == 50 for r in runs)
    drain(pipeline)
    details = [db_client.get(f"/api/v1/evaluations/runs/{r['id']}").json() for r in runs]
    for d in details:
        assert d["status"] == "succeeded", d["error"]
        assert d["progress"] == 50
        agg = d["aggregate_metrics"]
        assert agg["cases"] == 50
        assert agg["retrieval_cases"] == 47  # 3 unanswerable cases have no retrieval labels
        for key in ("recall_at_k", "precision_at_k", "mrr", "ndcg_at_k"):
            assert 0 <= agg[key] <= 1
        assert agg["retrieval_ms_p50"] is not None
        assert d["config"]["embedding"]["dimension"] == 16
        assert d["config"]["machine"]["cpu_count"]
        assert len(d["results"]) == 50
    s1, s2, s3 = details
    assert s1["config"]["chunk_strategy"] == "fixed" and s1["config"]["mode"] == "dense"
    assert s3["config"]["mode"] == "hybrid"
    assert s3["config"]["rrf_k"] == 60
    hybrid_case = next(r for r in s3["results"] if r["retrieved"])
    assert set(hybrid_case["retrieved"][0]["ranks"]) <= {"dense", "lexical"}
    # Reproducible: rerunning S2 yields identical metrics.
    again = start(db_client, sample, preset="S2")
    drain(pipeline)
    repeat = db_client.get(f"/api/v1/evaluations/runs/{again['id']}").json()
    keys = ("recall_at_k", "precision_at_k", "mrr", "ndcg_at_k")
    assert {k: repeat["aggregate_metrics"][k] for k in keys} == {
        k: s2["aggregate_metrics"][k] for k in keys
    }


def test_s4_needs_the_optional_reranker(
    db_client: TestClient, sample: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rr, "available", lambda: False)
    r = db_client.post(
        "/api/v1/evaluations/runs", json={"dataset_id": sample, "config": {"preset": "S4"}}
    )
    assert r.status_code == 409
    assert "pip install" in r.json()["error"]["message"]


def test_s4_with_a_reranker_records_rerank_ranks(
    db_client: TestClient,
    pipeline: Pipeline,
    sample: str,
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Fake:
        name = "fake-reranker"

        def score(self, query: str, passages: list[str]) -> list[float]:
            words = set(query.lower().split())
            return [float(len(words & set(p.lower().split()))) for p in passages]

    monkeypatch.setattr(rr, "available", lambda: True)
    created = start(db_client, sample, preset="S4", split="test")
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    with Session(db_engine) as s:
        assert runner.claim_next_run(s) == uuid.UUID(created["id"])
    runner.execute_run(
        factory,
        get_settings(),
        uuid.UUID(created["id"]),
        chat_factory=lambda s: chat_model(s, get_settings()),
        reranker=Fake(),
    )
    detail = db_client.get(f"/api/v1/evaluations/runs/{created['id']}").json()
    assert detail["status"] == "succeeded"
    assert detail["total"] == 12
    first = next(r for r in detail["results"] if r["retrieved"])
    assert first["retrieved"][0]["ranks"]["rerank"] == 1
    assert "rerank" in first["metrics"]


def test_answer_generation_measures_abstention_and_injection(
    db_client: TestClient, pipeline: Pipeline, sample: str, fake_ollama: FakeOllama
) -> None:
    # Fake model: answers with a citation for everything except questions it "can't" answer.
    for _ in range(60):
        fake_ollama.chat_replies.append(
            json.dumps({"answer": "It is stated here [1].", "citations": [1], "abstained": False})
        )
    created = start(db_client, sample, preset="S3", split="test", generate_answers=True, top_k=3)
    drain(pipeline)
    detail = db_client.get(f"/api/v1/evaluations/runs/{created['id']}").json()
    assert detail["status"] == "succeeded", detail["error"]
    agg = detail["aggregate_metrics"]
    assert agg["abstention_correct_n"] == 12
    assert agg["citation_precision_n"] >= 1
    assert detail["config"]["generation"]["prompt_version"] == "rag-answer-v2"
    unanswerable = [r for r in detail["results"] if not r["answerable"]]
    for r in unanswerable:  # the fake model never abstains, so these are scored as failures
        assert r["metrics"]["abstention_correct"] == 0.0
        assert r["failure_category"] == "should_have_abstained"


def test_export_and_dataset_lock(db_client: TestClient, pipeline: Pipeline, sample: str) -> None:
    created = start(db_client, sample, preset="S2", split="test")
    drain(pipeline)
    exported = db_client.get(
        f"/api/v1/evaluations/runs/{created['id']}/export", params={"format": "csv"}
    )
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert rows[1][:3] == ["case_id", "split", "question"]
    assert len(rows) == 2 + 12
    as_json = db_client.get(f"/api/v1/evaluations/runs/{created['id']}/export").json()
    assert as_json["config"]["dataset"] == {
        "name": "Northwind gold set",
        "version": "v1",
        "cases": 12,
    }

    locked = db_client.post(
        f"/api/v1/evaluations/datasets/{sample}/cases/import",
        files={
            "file": ("more.jsonl", b'{"question": "x", "answerable": false}', "application/json")
        },
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "dataset_locked"


def test_custom_dataset_import_and_validation(
    db_client: TestClient, fake_ollama: FakeOllama
) -> None:
    ds = db_client.post(
        "/api/v1/evaluations/datasets", json={"name": "Mine", "version": "v1"}
    ).json()
    dup = db_client.post("/api/v1/evaluations/datasets", json={"name": "Mine", "version": "v1"})
    assert dup.status_code == 409
    content = (
        b'{"id": "a", "question": "q?", "expected_evidence": [{"document": "x.md"}]}\n{"id": "b"}\n'
    )
    summary = db_client.post(
        f"/api/v1/evaluations/datasets/{ds['id']}/cases/import",
        files={"file": ("cases.jsonl", content, "application/json")},
    ).json()
    assert summary["imported"] == 1
    assert summary["errors"][0]["row"] == 2
    detail = db_client.get(f"/api/v1/evaluations/datasets/{ds['id']}").json()
    assert detail["missing_documents"] == ["x.md"]
    # No embeddings in this workspace yet: a dense run explains why it can't start.
    r = db_client.post(
        "/api/v1/evaluations/runs", json={"dataset_id": ds["id"], "config": {"preset": "S2"}}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_embeddings"


def test_interrupted_run_resumes_without_rescoring(
    db_client: TestClient, pipeline: Pipeline, sample: str, db_engine: Engine
) -> None:
    created = start(db_client, sample, preset="S2", split="test")
    run_id = uuid.UUID(created["id"])
    with Session(db_engine) as s:
        assert runner.claim_next_run(s) == run_id
    # Score 4 cases, then "crash".
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    with factory() as s:
        run_row = s.get(EvaluationRun, run_id)
        assert run_row is not None
        cases = runner._cases(s, run_row.dataset_id, "test")[:4]
        for case in cases:
            s.add(runner.score_case(s, get_settings(), run_row, case, None, None))
        run_row.progress = 4
        run_row.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
        s.commit()
    drain(pipeline)  # recovers the stale run and finishes the remaining 8
    with Session(db_engine) as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(EvaluationResult)
                .where(EvaluationResult.run_id == run_id)
            )
            == 12
        )
    assert db_client.get(f"/api/v1/evaluations/runs/{run_id}").json()["status"] == "succeeded"
