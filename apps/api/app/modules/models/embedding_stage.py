"""Ingestion stage 3: embed chunks locally in batches and store them with their version (M3).

The embedding text is the section path plus the chunk text, so headings contribute to meaning.
Vectors are validated (dimension, finite) per batch, and the job heartbeat is refreshed between
batches so a long CPU embedding run is never mistaken for a crashed worker.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import insert, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import ChunkEmbedding, IngestionJob
from app.modules.documents.chunking import Chunk
from app.modules.models.interfaces import ModelError
from app.modules.models.registry import (
    OllamaEmbedding,
    client_for,
    effective_models,
    ensure_embedding_version,
)
from app.workers.ingestion import EmbeddedChunks, IngestionError, Pipeline


def embedding_text(chunk: Chunk) -> str:
    return f"{chunk.section_path}\n{chunk.text}" if chunk.section_path else chunk.text


def attach_embedding(pipeline: Pipeline) -> None:
    settings = pipeline.settings

    def embed(
        factory: sessionmaker[Session], chunks: list[Chunk], job_id: uuid.UUID
    ) -> EmbeddedChunks:
        client = client_for(settings)
        try:
            with factory() as session:
                model = effective_models(session, settings).embedding_model
                version = ensure_embedding_version(session, client, model)
                version_id = version.id
                embedder = OllamaEmbedding(client, version, settings.embedding_batch_size)
            vectors: dict[tuple[str, int], list[float]] = {}
            size = settings.embedding_batch_size
            for start in range(0, len(chunks), size):
                batch = chunks[start : start + size]
                for c, v in zip(
                    batch, embedder.embed_documents([embedding_text(c) for c in batch]), strict=True
                ):
                    vectors[(c.strategy, c.index)] = v
                with factory() as session:
                    session.execute(
                        update(IngestionJob)
                        .where(IngestionJob.id == job_id)
                        .values(heartbeat_at=datetime.now(UTC))
                    )
                    session.commit()
        except ModelError as exc:
            raise IngestionError(exc.code, exc.message, retryable=exc.retryable) from exc
        return EmbeddedChunks(version_id=version_id, vectors=vectors)

    def store(
        session: Session,
        ids: dict[tuple[str, int], uuid.UUID],
        embedded: EmbeddedChunks,
        workspace_id: uuid.UUID,
    ) -> None:
        rows = [
            {
                "chunk_id": ids[key],
                "embedding_version_id": embedded.version_id,
                "workspace_id": workspace_id,
                "embedding": vector,
            }
            for key, vector in embedded.vectors.items()
        ]
        if rows:
            session.execute(insert(ChunkEmbedding), rows)

    pipeline.embedder = embed
    pipeline.store_vectors = store
