"""Evaluation runs (TRD §9, PRD §5.4): created by the API, executed by the worker, case by case.

- Each case's result is committed as soon as it's computed, so progress is real and a run that
  was interrupted resumes from the cases it hasn't scored yet.
- The run's `config` records everything needed to reproduce it: dataset version, retrieval
  knobs, embedding model + digest + dimension, generation model + prompt version (when answers
  are generated) and the machine profile.
- Retrieval is always measured. Answer generation is optional: on a CPU it costs tens of seconds
  per case, so the UI says so before it's enabled.
"""

import ctypes
import logging
import os
import platform
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
)
from app.modules.evaluation import metrics as m
from app.modules.models import reranker as rr
from app.modules.models.interfaces import ChatModel, ModelError
from app.modules.models.registry import active_embedding_version, effective_models
from app.modules.rag.answer import answer_question
from app.modules.rag.prompts import PROMPT_VERSION
from app.modules.retrieval.service import RetrievalConfig, retrieve
from app.modules.retrieval.types import Scope

logger = logging.getLogger(__name__)

Preset = Literal["S1", "S2", "S3", "S4", "custom"]
PRESETS: dict[str, dict[str, Any]] = {
    "S1": {"chunk_strategy": "fixed", "mode": "dense", "rerank": False},
    "S2": {"chunk_strategy": "recursive", "mode": "dense", "rerank": False},
    "S3": {"chunk_strategy": "recursive", "mode": "hybrid", "rerank": False},
    "S4": {"chunk_strategy": "recursive", "mode": "hybrid", "rerank": True},
}
PRESET_LABELS = {
    "S1": "S1 fixed + dense",
    "S2": "S2 recursive + dense",
    "S3": "S3 recursive + hybrid (RRF)",
    "S4": "S4 hybrid + reranker",
}


class RunConfigIn(BaseModel):
    preset: Preset = "S2"
    chunk_strategy: Literal["fixed", "recursive"] = "recursive"
    mode: Literal["dense", "lexical", "hybrid"] = "dense"
    rerank: bool = False
    top_k: int = Field(default=5, ge=1, le=20)
    candidates: int = Field(default=20, ge=1, le=100)
    split: Literal["dev", "test", "all"] = "all"
    generate_answers: bool = False
    label: str | None = Field(default=None, max_length=80)

    def resolved(self) -> "RunConfigIn":
        if self.preset == "custom":
            return self
        return self.model_copy(update=PRESETS[self.preset])


def machine_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }
    try:
        if sys.platform == "win32":

            class _Mem(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = _Mem()
            mem.dwLength = ctypes.sizeof(_Mem)
            kernel32 = ctypes.windll.kernel32  # win32-only branch
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            profile["ram_total_gb"] = round(mem.ullTotalPhys / 1024**3, 1)
            profile["ram_available_gb_at_start"] = round(mem.ullAvailPhys / 1024**3, 1)
        else:
            with open("/proc/meminfo", encoding="ascii") as f:
                info = dict(line.split(":", 1) for line in f)
            profile["ram_total_gb"] = round(int(info["MemTotal"].split()[0]) / 1024**2, 1)
    except (OSError, KeyError, ValueError, AttributeError):
        pass
    return profile


def _cases(session: Session, dataset_id: uuid.UUID, split: str) -> list[EvaluationCase]:
    stmt = select(EvaluationCase).where(EvaluationCase.dataset_id == dataset_id)
    if split != "all":
        stmt = stmt.where(EvaluationCase.split == split)
    return list(session.scalars(stmt.order_by(EvaluationCase.external_id)))


def create_run(
    session: Session,
    settings: Settings,
    workspace_id: uuid.UUID,
    dataset_id: uuid.UUID,
    cfg_in: RunConfigIn,
) -> EvaluationRun:
    dataset = session.scalar(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id, EvaluationDataset.workspace_id == workspace_id
        )
    )
    if dataset is None:
        raise AppError("dataset_not_found", "This evaluation dataset doesn't exist.", 404)
    cfg = cfg_in.resolved()
    if cfg.rerank and not rr.available():
        raise AppError(
            "reranker_unavailable",
            "This configuration needs the optional reranker, which isn't installed. "
            'Run: pip install -e "apps/api[reranker]"',
            409,
        )
    version = active_embedding_version(session)
    if cfg.mode in ("dense", "hybrid") and version is None:
        raise AppError(
            "no_embeddings",
            "No documents have been embedded yet. Index the dataset's documents first.",
            409,
        )
    cases = _cases(session, dataset.id, cfg.split)
    if not cases:
        raise AppError(
            "dataset_empty", "There are no cases in this split. Import cases first.", 409
        )
    models = effective_models(session, settings)
    config: dict[str, Any] = {
        **cfg.model_dump(),
        "dataset": {"name": dataset.name, "version": dataset.version, "cases": len(cases)},
        "rrf_k": settings.rrf_k,
        "embedding": {
            "model": version.model,
            "digest": version.digest,
            "dimension": version.dimension,
        }
        if version
        else None,
        "reranker_model": settings.reranker_model if cfg.rerank else None,
        "generation": {
            "model": models.generation_model,
            "prompt_version": PROMPT_VERSION,
            "temperature": settings.rag_temperature,
            "context_chars": settings.rag_context_chars,
            "min_dense_score": settings.rag_min_dense_score,
        }
        if cfg.generate_answers
        else None,
        "machine": machine_profile(),
    }
    label = cfg_in.label or (
        PRESET_LABELS.get(cfg.preset, f"{cfg.chunk_strategy} + {cfg.mode}")
        + (" + answers" if cfg.generate_answers else "")
    )
    run = EvaluationRun(
        id=uuid.uuid4(),
        dataset_id=dataset.id,
        workspace_id=workspace_id,
        label=label,
        config=config,
        strategy=cfg.preset if cfg.preset != "custom" else f"{cfg.chunk_strategy}/{cfg.mode}",
        model_id=f"{version.model}@{version.digest[:12]}" if version else None,
        status="queued",
        total=len(cases),
    )
    session.add(run)
    session.commit()
    return run


# --- Worker side ---


def recover_stale_runs(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.job_stale_seconds)
    stale = session.scalars(
        select(EvaluationRun)
        .where(EvaluationRun.status == "running", EvaluationRun.heartbeat_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    for run in stale:
        run.status = "queued"  # resumes from the cases that have no result yet
    session.commit()
    return len(stale)


def claim_next_run(session: Session) -> uuid.UUID | None:
    run = session.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.status == "queued")
        .order_by(EvaluationRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is None:
        session.rollback()
        return None
    now = datetime.now(UTC)
    run.status = "running"
    run.started_at = run.started_at or now
    run.heartbeat_at = now
    session.commit()
    return run.id


def _failure(metrics: dict[str, Any], answerable: bool) -> str | None:
    if metrics.get("injection_resisted") == 0:
        return "injection_followed"
    if metrics.get("abstention_correct") == 0:
        return "wrong_abstention" if answerable else "should_have_abstained"
    if answerable and metrics.get("hit_at_k") == 0:
        return "evidence_not_retrieved"
    if answerable and (metrics.get("recall_at_k") or 0) < 1:
        return "partial_recall"
    if metrics.get("citation_precision") is not None and float(metrics["citation_precision"]) < 1:
        return "irrelevant_citation"
    return None


def score_case(
    session: Session,
    settings: Settings,
    run: EvaluationRun,
    case: EvaluationCase,
    chat: ChatModel | None,
    reranker: rr.Reranker | None,
) -> EvaluationResult:
    cfg = RunConfigIn.model_validate(
        {k: v for k, v in run.config.items() if k in RunConfigIn.model_fields}
    )
    started = time.perf_counter()
    result = retrieve(
        session,
        settings,
        case.question,
        RetrievalConfig(
            mode=cfg.mode,
            strategy=cfg.chunk_strategy,
            top_k=cfg.top_k,
            candidates=cfg.candidates,
            rerank=cfg.rerank,
            rrf_k=int(run.config.get("rrf_k", settings.rrf_k)),  # type: ignore[call-overload]
        ),
        Scope(workspace_id=run.workspace_id, strategy=cfg.chunk_strategy),
        reranker=reranker,
    )
    retrieval_ms = round((time.perf_counter() - started) * 1000)
    retrieved = [
        m.Retrieved(str(c.chunk_id), c.document_name, c.text, c.page_start, c.page_end)
        for c in result.candidates
    ]
    relevant, _ = m.relevance(retrieved, case.expected_evidence, case.expected_chunk_ids)
    metrics: dict[str, Any] = {"retrieval_ms": retrieval_ms, **result.timings_ms}
    if case.answerable:
        metrics.update(
            m.retrieval_metrics(
                retrieved, case.expected_evidence, case.expected_chunk_ids, cfg.top_k
            )
        )

    answer_text: str | None = None
    if chat is not None:
        grounded = answer_question(
            case.question,
            result.candidates,
            chat,
            max_context_chars=settings.rag_context_chars,
            min_score=settings.rag_min_dense_score
            if result.mode == "dense" and settings.rag_min_dense_score >= 0
            else None,
            temperature=settings.rag_temperature,
        )
        answer_text = grounded.text
        metrics["abstained"] = grounded.abstained
        metrics["abstention_correct"] = 1.0 if grounded.abstained != case.answerable else 0.0
        if grounded.citations and case.answerable:
            cited = [
                m.Retrieved(
                    str(c.candidate.chunk_id),
                    c.candidate.document_name,
                    c.candidate.text,
                    c.candidate.page_start,
                    c.candidate.page_end,
                )
                for c in grounded.citations
            ]
            rel, _ = m.relevance(cited, case.expected_evidence, case.expected_chunk_ids)
            metrics["citation_precision"] = round(sum(rel) / len(rel), 4)
        if "injection" in case.tags:
            metrics["injection_resisted"] = (
                0.0 if m.INJECTION_MARKER in grounded.text.upper() else 1.0
            )
        if grounded.generation_ms is not None:
            metrics["generation"] = grounded.generation_ms

    return EvaluationResult(
        run_id=run.id,
        case_id=case.id,
        retrieved_ids=[
            {
                "chunk_id": str(c.chunk_id),
                "document_name": c.document_name,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "section_path": c.section_path,
                "score": round(c.score, 4),
                "ranks": c.ranks,
                "relevant": is_rel,
                "excerpt": c.text[:600],
            }
            for c, is_rel in zip(result.candidates, relevant, strict=True)
        ],
        answer=answer_text,
        metrics=metrics,
        failure_category=_failure(metrics, case.answerable),
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def execute_run(
    factory: sessionmaker[Session],
    settings: Settings,
    run_id: uuid.UUID,
    *,
    chat_factory: Callable[[Session], ChatModel],
    reranker: rr.Reranker | None = None,
) -> None:
    with factory() as session:
        run = session.get(EvaluationRun, run_id)
        if run is None:
            return
        done = set(
            session.scalars(
                select(EvaluationResult.case_id).where(EvaluationResult.run_id == run_id)
            )
        )
        split = str(run.config.get("split", "all"))
        cases = [c for c in _cases(session, run.dataset_id, split) if c.id not in done]
        generate = bool(run.config.get("generate_answers"))
        chat = chat_factory(session) if generate else None
        if run.config.get("rerank") and reranker is None:
            reranker = rr.get_reranker(
                str(run.config.get("reranker_model") or settings.reranker_model)
            )
        try:
            for case in cases:
                try:
                    result = score_case(session, settings, run, case, chat, reranker)
                except (ModelError, AppError) as exc:
                    session.rollback()
                    code = exc.code
                    if code in (
                        "no_embeddings",
                        "reranker_unavailable",
                        "ollama_unavailable",
                        "model_missing",
                    ):
                        raise  # the whole run can't proceed
                    result = EvaluationResult(
                        run_id=run.id,
                        case_id=case.id,
                        metrics={},
                        error=exc.message,
                        failure_category="error",
                    )
                session.add(result)
                run.progress = len(done) + 1
                done.add(case.id)
                run.heartbeat_at = datetime.now(UTC)
                session.commit()
            rows = session.scalars(
                select(EvaluationResult).where(EvaluationResult.run_id == run_id)
            ).all()
            run.aggregate_metrics = m.aggregate(
                [
                    {
                        "metrics": r.metrics,
                        "latency_ms": r.latency_ms,
                        "error": r.error,
                        "failure_category": r.failure_category,
                    }
                    for r in rows
                ]
            )
            run.status = "succeeded"
            run.progress = run.total
            run.completed_at = datetime.now(UTC)
            session.commit()
            logger.info("evaluation_succeeded", extra={"run_id": str(run_id), "cases": len(rows)})
        except (ModelError, AppError) as exc:
            session.rollback()
            run = session.get(EvaluationRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error = exc.message
                run.completed_at = datetime.now(UTC)
                session.commit()
            logger.warning(
                "evaluation_failed", extra={"run_id": str(run_id), "error_code": exc.code}
            )
