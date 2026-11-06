"""One entry point for retrieval, shared by RAG and the Evaluation Lab (TRD §6.2, §9).

Strategies (TRD §9):
- S1 fixed chunks + dense      - S3 recursive + dense + lexical, fused with RRF
- S2 recursive chunks + dense  - S4 S3 + local CrossEncoder reranker

`retrieve` returns ranked candidates and a trace (mode, per-stage latency) that is stored with
answers and evaluation results.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.models.interfaces import ModelError
from app.modules.models.registry import active_embedding_version, query_embedder
from app.modules.models.reranker import Reranker, get_reranker, rerank
from app.modules.retrieval.dense import dense_search
from app.modules.retrieval.fusion import rrf
from app.modules.retrieval.lexical import lexical_search
from app.modules.retrieval.types import Candidate, ChunkStrategy, Scope

RetrievalMode = Literal["dense", "lexical", "hybrid"]


@dataclass(frozen=True)
class RetrievalConfig:
    mode: RetrievalMode = "dense"
    strategy: ChunkStrategy = "recursive"
    top_k: int = 6
    # How many candidates each retriever returns before fusion / reranking.
    candidates: int = 20
    rerank: bool = False
    rrf_k: int = 60


@dataclass
class RetrievalResult:
    candidates: list[Candidate]
    mode: str
    strategy: ChunkStrategy
    timings_ms: dict[str, int] = field(default_factory=dict)
    embedding_version_id: uuid.UUID | None = None
    reranked: bool = False


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _dense(
    session: Session,
    settings: Settings,
    question: str,
    scope: Scope,
    limit: int,
    timings: dict[str, int],
) -> tuple[list[Candidate], uuid.UUID]:
    version = active_embedding_version(session)
    embedder = query_embedder(session, settings)
    if version is None or embedder is None:
        raise AppError(
            "no_embeddings",
            "No documents have been indexed yet. Upload a document and start the worker.",
            409,
        )
    started = time.perf_counter()
    try:
        vector = embedder.embed_query(question)
    except ModelError as exc:
        raise AppError(exc.code, exc.message, 503) from exc
    timings["embed_query"] = _ms(started)
    started = time.perf_counter()
    hits = dense_search(session, vector, version.id, scope, limit)
    timings["dense"] = _ms(started)
    return hits, version.id


def retrieve(
    session: Session,
    settings: Settings,
    question: str,
    config: RetrievalConfig,
    scope: Scope,
    *,
    reranker: Reranker | None = None,
) -> RetrievalResult:
    timings: dict[str, int] = {}
    version_id: uuid.UUID | None = None
    if config.mode == "lexical":
        started = time.perf_counter()
        hits = lexical_search(session, question, scope, config.candidates)
        timings["lexical"] = _ms(started)
    elif config.mode == "dense":
        hits, version_id = _dense(session, settings, question, scope, config.candidates, timings)
    else:
        dense_hits, version_id = _dense(
            session, settings, question, scope, config.candidates, timings
        )
        started = time.perf_counter()
        lexical_hits = lexical_search(session, question, scope, config.candidates)
        timings["lexical"] = _ms(started)
        started = time.perf_counter()
        hits = rrf({"dense": dense_hits, "lexical": lexical_hits}, k=config.rrf_k)
        timings["fusion"] = _ms(started)

    if config.rerank:
        model = reranker or get_reranker(settings.reranker_model)
        started = time.perf_counter()
        try:
            hits = rerank(model, question, hits[: config.candidates])
        except ModelError as exc:
            raise AppError(exc.code, exc.message, 409) from exc
        timings["rerank"] = _ms(started)

    return RetrievalResult(
        hits[: config.top_k],
        config.mode + ("+rerank" if config.rerank else ""),
        config.strategy,
        timings,
        version_id,
        config.rerank,
    )
