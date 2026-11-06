"""TRD §9: deterministic retrieval metrics, RRF fusion, reranking and case import."""

import json
import uuid

import pytest

from app.modules.evaluation import metrics as m
from app.modules.evaluation.importer import parse_cases
from app.modules.models.reranker import rerank
from app.modules.retrieval.fusion import rrf
from app.modules.retrieval.types import Candidate

DOC = "policy.md"


def r(text: str, doc: str = DOC, page: int | None = None, cid: str | None = None) -> m.Retrieved:
    return m.Retrieved(cid or uuid.uuid4().hex, doc, text, page, page)


def test_relevance_needs_the_document_and_the_quote() -> None:
    ev = {"document": "Policy.md", "quote": "capped at 150  EUR"}
    assert m.matches(r("Hotels are Capped at 150 EUR per night."), ev)
    assert not m.matches(r("Hotels are capped at 150 EUR.", doc="other.md"), ev)
    assert not m.matches(r("Meals are 40 EUR."), ev)
    assert m.matches(r("anything", page=3), {"document": DOC, "page": 3})
    assert not m.matches(r("anything", page=4), {"document": DOC, "page": 3})


def test_metrics_for_a_known_ranking() -> None:
    ev = [{"document": DOC, "quote": "alpha"}, {"document": DOC, "quote": "beta"}]
    ranked = [r("noise"), r("alpha one"), r("alpha again"), r("beta"), r("noise")]
    out = m.retrieval_metrics(ranked, ev, [], k=5)
    assert out["recall_at_k"] == 1.0
    assert out["precision_at_k"] == 0.6  # 3 relevant chunks of 5
    assert out["mrr"] == 0.5  # first relevant at rank 2
    # duplicates of "alpha" don't add gain: gains at ranks 2 and 4 only
    dcg = 1 / m.math.log2(3) + 1 / m.math.log2(5)
    ideal = 1 / m.math.log2(2) + 1 / m.math.log2(3)
    assert out["ndcg_at_k"] == round(dcg / ideal, 4)
    assert m.retrieval_metrics(ranked, ev, [], k=2)["recall_at_k"] == 0.5


def test_no_relevant_results_score_zero() -> None:
    out = m.retrieval_metrics([r("noise")], [{"document": DOC, "quote": "x"}], [], k=3)
    assert out == {
        "recall_at_k": 0.0,
        "precision_at_k": 0.0,
        "mrr": 0.0,
        "ndcg_at_k": 0.0,
        "hit_at_k": 0.0,
    }


def test_raw_chunk_ids_also_count() -> None:
    out = m.retrieval_metrics([r("x", cid="c-1")], [], ["c-1"], k=1)
    assert out["recall_at_k"] == 1.0
    assert out["mrr"] == 1.0


def test_aggregate_reports_sample_counts_and_percentiles() -> None:
    results = [
        {
            "metrics": {
                "recall_at_k": 1.0,
                "precision_at_k": 0.2,
                "mrr": 1.0,
                "ndcg_at_k": 1.0,
                "hit_at_k": 1.0,
                "retrieval_ms": 100,
                "abstention_correct": 1.0,
            },
            "latency_ms": 100,
        },
        {
            "metrics": {
                "recall_at_k": 0.0,
                "precision_at_k": 0.0,
                "mrr": 0.0,
                "ndcg_at_k": 0.0,
                "hit_at_k": 0.0,
                "retrieval_ms": 300,
            },
            "latency_ms": 300,
            "failure_category": "evidence_not_retrieved",
        },
        {
            "metrics": {"retrieval_ms": 200, "abstention_correct": 0.0},
            "latency_ms": 200,
        },  # unanswerable
    ]
    agg = m.aggregate(results)
    assert agg["cases"] == 3
    assert agg["retrieval_cases"] == 2
    assert agg["recall_at_k"] == 0.5
    assert agg["abstention_correct"] == 0.5
    assert agg["abstention_correct_n"] == 2
    assert agg["citation_precision"] is None
    assert agg["retrieval_ms_p50"] == 200
    assert agg["failure_categories"] == {"evidence_not_retrieved": 1}


def cand(name: str) -> Candidate:
    return Candidate(
        uuid.uuid5(uuid.NAMESPACE_DNS, name), uuid.uuid4(), "d", name, None, None, None, 0, 0.0
    )


def test_rrf_rewards_agreement_between_retrievers() -> None:
    a, b, c = cand("a"), cand("b"), cand("c")
    fused = rrf({"dense": [a, b], "lexical": [c, b]}, k=60)
    assert fused[0].text == "b"  # in both lists
    assert fused[0].ranks == {"dense": 2, "lexical": 2}
    assert fused[0].score == pytest.approx(2 / 62)
    assert a.ranks == {}  # inputs are not mutated


def test_rerank_reorders_and_records_ranks() -> None:
    class Fake:
        name = "fake"

        def score(self, query: str, passages: list[str]) -> list[float]:
            return [float(len(p)) for p in passages]

    out = rerank(Fake(), "q", [cand("bb"), cand("a"), cand("ccc")])
    assert [c.text for c in out] == ["ccc", "bb", "a"]
    assert out[0].ranks["rerank"] == 1


def test_jsonl_import_with_row_errors() -> None:
    rows = [
        {
            "id": "q1",
            "question": "Hotel cap?",
            "expected_evidence": [{"document": DOC, "quote": "150"}],
        },
        {"id": "q2", "question": "Unknown?", "answerable": False},
        {"id": "q1", "question": "dup", "expected_evidence": [{"document": DOC}]},
        {"id": "q4", "question": "no evidence"},
        {"id": "q5", "question": " ", "expected_evidence": [{"document": DOC}]},
        {"id": "q6", "question": "x", "split": "train", "expected_evidence": [{"document": DOC}]},
    ]
    content = ("\n".join(json.dumps(x) for x in rows) + "\nnot json\n").encode()
    cases, errors = parse_cases("set.jsonl", content)
    assert [c.id for c in cases] == ["q1", "q2"]
    messages = {e.row: e.message for e in errors}
    assert "Duplicate id" in messages[3]
    assert "need expected_evidence" in messages[4]
    assert "question" in messages[5]
    assert "split" in messages[6]
    assert "Invalid JSON" in messages[7]


def test_csv_import_with_simple_evidence_columns() -> None:
    csv_text = (
        "id,split,question,answerable,evidence_document,evidence_quote,evidence_page,tags\n"
        'q1,test,"Hotel cap?",true,policy.md,capped at 150,2,factual;exact\n'
        "q2,dev,Unknown?,false,,,,unanswerable\n"
    )
    cases, errors = parse_cases("set.csv", csv_text.encode())
    assert errors == []
    assert cases[0].split == "test"
    assert cases[0].expected_evidence[0].page == 2
    assert cases[0].tags == ["factual", "exact"]
    assert cases[1].answerable is False


def test_import_rejects_wrong_type_and_missing_question_column() -> None:
    assert parse_cases("set.xlsx", b"x")[1][0].message == "Upload a .jsonl or .csv file."
    assert "question" in parse_cases("set.csv", b"id,text\n1,x\n")[1][0].message
