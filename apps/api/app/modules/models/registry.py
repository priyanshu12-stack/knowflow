"""Which local models are in use, and the embedding space they define (PRD §5.6, TRD §4.2).

- `effective_models` merges the saved `model_settings` row over the `.env` defaults.
- `ensure_embedding_version` probes the embedding model once (digest + real vector dimension),
  records an `embedding_versions` row and makes it the active one. The dimension is never assumed.
- `OllamaEmbedding` / `OllamaChat` implement the provider-agnostic interfaces.
"""

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import EmbeddingVersion, ModelSettings
from app.modules.models.interfaces import ChatMessage, ChatResult, ModelError
from app.modules.models.ollama import OllamaClient, validate_vectors

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectiveModels:
    generation_model: str
    embedding_model: str
    reranker_enabled: bool


def effective_models(session: Session, settings: Settings) -> EffectiveModels:
    row = session.get(ModelSettings, 1)
    if row is None:
        return EffectiveModels(
            settings.ollama_generation_model,
            settings.ollama_embedding_model,
            settings.enable_reranker,
        )
    return EffectiveModels(row.generation_model, row.embedding_model, row.reranker_enabled)


@lru_cache(maxsize=4)
def ollama_client(base_url: str, timeout: float) -> OllamaClient:
    return OllamaClient(base_url, timeout=timeout)


def client_for(settings: Settings) -> OllamaClient:
    return ollama_client(settings.ollama_base_url, settings.embedding_timeout_seconds)


def task_prefixes(model: str) -> tuple[str, str]:
    """nomic-embed-text is trained with task prefixes; without them retrieval quality drops."""
    if "nomic-embed" in model:
        return "search_document: ", "search_query: "
    return "", ""


def model_digest(client: OllamaClient, model: str) -> str:
    for m in client.list_models():
        if m.name == model:
            return m.digest
    raise ModelError(
        "model_missing", f"{model} is not installed. Run: ollama pull {model}", retryable=True
    )


def probe_dimension(client: OllamaClient, model: str) -> int:
    doc_prefix, _ = task_prefixes(model)
    return validate_vectors(client.embed(model, [f"{doc_prefix}dimension probe"]), None)


def active_embedding_version(session: Session) -> EmbeddingVersion | None:
    return session.scalar(select(EmbeddingVersion).where(EmbeddingVersion.is_active))


def ensure_embedding_version(
    session: Session, client: OllamaClient, model: str
) -> EmbeddingVersion:
    """Return the active version for `model`, probing and activating a new one when needed."""
    digest = model_digest(client, model)
    active = active_embedding_version(session)
    if active is not None and active.model == model and active.digest == digest:
        return active
    dimension = probe_dimension(client, model)
    version = session.scalar(
        select(EmbeddingVersion).where(
            EmbeddingVersion.model == model,
            EmbeddingVersion.digest == digest,
            EmbeddingVersion.dimension == dimension,
        )
    )
    doc_prefix, query_prefix = task_prefixes(model)
    if version is None:
        version = EmbeddingVersion(
            id=uuid.uuid4(),
            model=model,
            digest=digest,
            dimension=dimension,
            document_prefix=doc_prefix,
            query_prefix=query_prefix,
        )
        session.add(version)
    session.execute(update(EmbeddingVersion).values(is_active=False))
    session.flush()
    version.is_active = True
    session.commit()
    logger.info(
        "embedding_version_activated",
        extra={"model": model, "digest": digest[:12], "dimension": dimension},
    )
    return version


class OllamaEmbedding:
    def __init__(self, client: OllamaClient, version: EmbeddingVersion, batch_size: int) -> None:
        self.client = client
        self.name = version.model
        self.dimension = version.dimension
        self.document_prefix = version.document_prefix
        self.query_prefix = version.query_prefix
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [self.document_prefix + t for t in texts[start : start + self.batch_size]]
            vectors = self.client.embed(self.name, batch)
            validate_vectors(vectors, self.dimension)
            out.extend(vectors)
        return out

    def embed_query(self, text: str) -> list[float]:
        vectors = self.client.embed(self.name, [self.query_prefix + text])
        validate_vectors(vectors, self.dimension)
        return vectors[0]


class OllamaChat:
    def __init__(self, client: OllamaClient, model: str, settings: Settings) -> None:
        self.client = client
        self.name = model
        self.settings = settings

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        json_schema: dict[str, Any] | None = None,
        num_predict: int = 768,
    ) -> ChatResult:
        return self.client.chat(
            self.name,
            messages,
            temperature=temperature,
            json_schema=json_schema,
            num_ctx=self.settings.generation_num_ctx,
            num_predict=num_predict,
            timeout=self.settings.generation_timeout_seconds,
        )


def chat_model(session: Session, settings: Settings) -> OllamaChat:
    models = effective_models(session, settings)
    client = ollama_client(settings.ollama_base_url, settings.generation_timeout_seconds)
    return OllamaChat(client, models.generation_model, settings)


def query_embedder(session: Session, settings: Settings) -> OllamaEmbedding | None:
    """Embedder for queries in the *active* space, or None when nothing is embedded yet."""
    version = active_embedding_version(session)
    if version is None:
        return None
    return OllamaEmbedding(client_for(settings), version, settings.embedding_batch_size)
