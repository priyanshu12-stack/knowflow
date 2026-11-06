"""Passage search over ready documents (lexical in M2; dense and hybrid join later)."""

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep, WorkspaceDep
from app.core.errors import AppError
from app.modules.models.interfaces import ModelError
from app.modules.models.registry import active_embedding_version, query_embedder
from app.modules.retrieval.dense import dense_search
from app.modules.retrieval.lexical import lexical_search
from app.modules.retrieval.types import Scope
from app.schemas.documents import ChunkStrategy
from app.schemas.search import SearchHit, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    session: SessionDep,
    workspace: WorkspaceDep,
    q: Annotated[str, Query(min_length=1, max_length=500, description="Search text")],
    settings: SettingsDep,
    strategy: ChunkStrategy = "recursive",
    mode: Literal["lexical", "dense"] = "lexical",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchResponse:
    scope = Scope(workspace_id=workspace.id, strategy=strategy)
    if mode == "dense":
        embedder = query_embedder(session, settings)
        version = active_embedding_version(session)
        if embedder is None or version is None:
            raise AppError(
                "no_embeddings",
                "No documents have been embedded yet. Upload a document and start the worker.",
                409,
            )
        try:
            vector = embedder.embed_query(q)
        except ModelError as exc:
            raise AppError(exc.code, exc.message, 503) from exc
        hits = dense_search(session, vector, version.id, scope, limit)
    else:
        hits = lexical_search(session, q, scope, limit)
    return SearchResponse(
        query=q,
        mode=mode,
        strategy=strategy,
        hits=[
            SearchHit(**{k: v for k, v in asdict(h).items() if k in SearchHit.model_fields})
            for h in hits
        ],
    )
