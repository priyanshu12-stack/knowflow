"""Dense retrieval with pgvector exact cosine search (TRD §3: exact first, HNSW only if measured).

Only vectors from the active embedding version are compared, and only for chunks of `ready`
documents in the caller's workspace.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document
from app.modules.retrieval.lexical import scoped, to_candidate
from app.modules.retrieval.types import Candidate, Scope


def dense_search(
    session: Session,
    query_vector: list[float],
    version_id: uuid.UUID,
    scope: Scope,
    limit: int,
) -> list[Candidate]:
    distance = ChunkEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk, Document.original_name, distance.label("distance"))
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            ChunkEmbedding.embedding_version_id == version_id,
            ChunkEmbedding.workspace_id == scope.workspace_id,
        )
        .order_by(distance, Chunk.id)
        .limit(limit)
    )
    rows = session.execute(scoped(stmt, scope)).all()
    return [
        to_candidate(chunk, name, 1.0 - float(dist), "dense", i)
        for i, (chunk, name, dist) in enumerate(rows, start=1)
    ]
