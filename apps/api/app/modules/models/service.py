"""Model settings use cases: inspect the local runtime, validate a selection, save it (PRD §5.6).

Validation is real: the embedding model is called to measure its dimension, and the generation
model must return a JSON object that matches a schema (TRD §4.3). Nothing is downloaded.
"""

import importlib.util
import time
import uuid

from pydantic import BaseModel, ValidationError
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Chunk, ChunkEmbedding, Document, IngestionJob, ModelSettings
from app.modules.documents.status import ACTIVE_JOB_STATUSES
from app.modules.models.interfaces import ChatMessage, ModelError
from app.modules.models.ollama import InstalledModel, OllamaClient, parse_json_object
from app.modules.models.registry import (
    active_embedding_version,
    effective_models,
    ensure_embedding_version,
    ollama_client,
    probe_dimension,
)
from app.schemas.settings import (
    EmbeddingVersionOut,
    InstalledModelOut,
    ModelSettingsOut,
    RerankerOut,
    RuntimeOut,
    SaveRequest,
    ValidateRequest,
    ValidateResponse,
    ValidationCheck,
)


def _client(settings: Settings) -> OllamaClient:
    return ollama_client(settings.ollama_base_url, settings.generation_timeout_seconds)


def _kind(m: InstalledModel) -> str:
    family = (m.family or "").lower()
    if "bert" in family or "embed" in m.name:
        return "embedding"
    return "generation" if family else "unknown"


def reranker_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def documents_needing_reindex(session: Session, workspace_id: uuid.UUID) -> int:
    """Ready documents with no vectors in the active embedding space."""
    version = active_embedding_version(session)
    ready = (
        select(func.count())
        .select_from(Document)
        .where(Document.workspace_id == workspace_id, Document.status == "ready")
    )
    if version is None:
        return session.scalar(ready) or 0
    embedded = (
        select(ChunkEmbedding.chunk_id)
        .join(Chunk, Chunk.id == ChunkEmbedding.chunk_id)
        .where(Chunk.document_id == Document.id, ChunkEmbedding.embedding_version_id == version.id)
    )
    return session.scalar(ready.where(~exists(embedded))) or 0


def describe(session: Session, settings: Settings, workspace_id: uuid.UUID) -> ModelSettingsOut:
    models = effective_models(session, settings)
    client = _client(settings)
    installed: list[InstalledModel] = []
    try:
        runtime = RuntimeOut(
            reachable=True, version=client.version(), base_url=settings.ollama_base_url
        )
        installed = client.list_models()
    except ModelError as exc:
        runtime = RuntimeOut(
            reachable=False, version=None, base_url=settings.ollama_base_url, error=exc.message
        )
    version = active_embedding_version(session)
    available = reranker_available()
    names = {m.name for m in installed}
    commands = [
        f"ollama pull {m}"
        for m in (models.generation_model, models.embedding_model)
        if m not in names
    ]
    if not available:
        commands.append('pip install -e "apps/api[reranker]"   # optional, ~2.3 GB')
    return ModelSettingsOut(
        runtime=runtime,
        installed=[InstalledModelOut(**m.__dict__, kind=_kind(m)) for m in installed],
        generation_model=models.generation_model,
        embedding_model=models.embedding_model,
        reranker=RerankerOut(
            enabled=models.reranker_enabled and available,
            available=available,
            model=settings.reranker_model,
            note=(
                "Optional second-stage scorer. CPU-heavy: it adds latency to every question."
                if available
                else "Not installed. Basic and hybrid search work without it."
            ),
        ),
        active_embedding=EmbeddingVersionOut(
            model=version.model,
            digest=version.digest,
            dimension=version.dimension,
            created_at=version.created_at,
        )
        if version
        else None,
        documents_needing_reindex=documents_needing_reindex(session, workspace_id),
        setup_commands=commands,
    )


class _Probe(BaseModel):
    ok: bool


_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


def validate(session: Session, settings: Settings, req: ValidateRequest) -> ValidateResponse:
    client = _client(settings)
    checks: list[ValidationCheck] = []
    try:
        installed = {m.name: m for m in client.list_models()}
    except ModelError as exc:
        return ValidateResponse(
            ok=False,
            checks=[ValidationCheck(name="runtime", state="failed", detail=exc.message)],
            embedding_dimension=None,
            embedding_model_changed=False,
        )
    checks.append(ValidationCheck(name="runtime", state="ok", detail="Ollama is reachable."))

    dimension: int | None = None
    if req.embedding_model not in installed:
        checks.append(
            ValidationCheck(
                name="embedding_model",
                state="failed",
                detail=f"Not installed. Run: ollama pull {req.embedding_model}",
            )
        )
    else:
        started = time.perf_counter()
        try:
            dimension = probe_dimension(client, req.embedding_model)
            checks.append(
                ValidationCheck(
                    name="embedding_model",
                    state="ok",
                    detail=f"Returns {dimension}-dimensional vectors.",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
            )
        except ModelError as exc:
            checks.append(
                ValidationCheck(name="embedding_model", state="failed", detail=exc.message)
            )

    if req.generation_model not in installed:
        checks.append(
            ValidationCheck(
                name="generation_model",
                state="failed",
                detail=f"Not installed. Run: ollama pull {req.generation_model}",
            )
        )
    elif not req.probe_generation:
        checks.append(
            ValidationCheck(
                name="generation_model", state="skipped", detail="Installed; probe skipped."
            )
        )
    else:
        started = time.perf_counter()
        try:
            result = client.chat(
                req.generation_model,
                [
                    ChatMessage("system", "Reply with JSON only."),
                    ChatMessage("user", 'Return {"ok": true}.'),
                ],
                temperature=0,
                json_schema=_PROBE_SCHEMA,
                num_ctx=1024,
                num_predict=32,
                timeout=settings.generation_timeout_seconds,
            )
            _Probe.model_validate(parse_json_object(result.content))
            checks.append(
                ValidationCheck(
                    name="generation_model",
                    state="ok",
                    detail="Returned valid structured JSON.",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
            )
        except (ModelError, ValidationError) as exc:
            detail = (
                exc.message if isinstance(exc, ModelError) else "Output didn't match the schema."
            )
            checks.append(ValidationCheck(name="generation_model", state="failed", detail=detail))

    active = active_embedding_version(session)
    changed = active is not None and (
        active.model != req.embedding_model
        or (dimension is not None and dimension != active.dimension)
    )
    return ValidateResponse(
        ok=all(c.state != "failed" for c in checks),
        checks=checks,
        embedding_dimension=dimension,
        embedding_model_changed=changed,
    )


def save(session: Session, settings: Settings, req: SaveRequest) -> bool:
    """Persist the selection. Returns True when existing vectors must be rebuilt."""
    client = _client(settings)
    try:
        installed = {m.name for m in client.list_models()}
    except ModelError as exc:
        raise AppError(exc.code, exc.message, 503) from exc
    missing = [m for m in (req.generation_model, req.embedding_model) if m not in installed]
    if missing:
        raise AppError(
            "model_missing",
            f"Not installed: {', '.join(missing)}. Pull it with ollama first.",
            422,
        )
    if req.reranker_enabled and not reranker_available():
        raise AppError(
            "reranker_unavailable",
            'The reranker is not installed. Run: pip install -e "apps/api[reranker]"',
            422,
        )
    previous = effective_models(session, settings).embedding_model
    row = session.get(ModelSettings, 1) or ModelSettings(id=1)
    row.generation_model = req.generation_model
    row.embedding_model = req.embedding_model
    row.reranker_enabled = req.reranker_enabled
    row.validation = {"saved_at": time.time()}
    session.add(row)
    session.commit()
    active = active_embedding_version(session)
    if previous != req.embedding_model or active is None or active.model != req.embedding_model:
        try:
            ensure_embedding_version(session, client, req.embedding_model)
        except ModelError as exc:
            raise AppError(exc.code, exc.message, 503) from exc
        return active is not None
    return False


def reindex_all(session: Session, workspace_id: uuid.UUID) -> int:
    """Queue every ready or failed document that isn't already queued/running."""
    busy = select(IngestionJob.document_id).where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
    docs = session.scalars(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.status.in_(("ready", "failed")),
            Document.id.not_in(busy),
        )
    ).all()
    for d in docs:
        session.add(IngestionJob(id=uuid.uuid4(), document_id=d.id, status="queued"))
        d.status = "queued"
    session.commit()
    return len(docs)
