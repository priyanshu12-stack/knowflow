"""One entry point for retrieval, shared by RAG and the Evaluation Lab (TRD §6.2, §9).

`RetrievalConfig` names the strategy (S1-S4) knobs; `retrieve` returns ranked candidates plus a
trace (mode, counts, per-stage latency) that is stored with answers and evaluation results.
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
from app.modules.retrieval.dense import dense_search
from app.modules.retrieval.lexical import lexical_search
from app.modules.retrieval.types import Candidate, ChunkStrategy, Scope

RetrievalMode = Literal["dense", "lexical"]


@dataclass(frozen=True)
class RetrievalConfig:
    mode: RetrievalMode = "dense"
    strategy: ChunkStrategy = "recursive"
    top_k: int = 6
    # How many candidates each retriever returns before fusion / packing.
    candidates: int = 20


@dataclass
class RetrievalResult:
    candidates: list[Candidate]
    mode: RetrievalMode
    strategy: ChunkStrategy
    timings_ms: dict[str, int] = field(default_factory=dict)
    embedding_version_id: uuid.UUID | None = None


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def retrieve(
    session: Session,
    settings: Settings,
    question: str,
    config: RetrievalConfig,
    scope: Scope,
) -> RetrievalResult:
    timings: dict[str, int] = {}
    if config.mode == "lexical":
        started = time.perf_counter()
        hits = lexical_search(session, question, scope, config.candidates)
        timings["lexical"] = _ms(started)
        return RetrievalResult(hits[: config.top_k], "lexical", config.strategy, timings)

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
    hits = dense_search(session, vector, version.id, scope, config.candidates)
    timings["dense"] = _ms(started)
    return RetrievalResult(hits[: config.top_k], "dense", config.strategy, timings, version.id)
