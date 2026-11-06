"""Passage search over ready documents (lexical in M2; dense and hybrid join later)."""

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, WorkspaceDep
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
    strategy: ChunkStrategy = "recursive",
    mode: Literal["lexical"] = "lexical",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchResponse:
    scope = Scope(workspace_id=workspace.id, strategy=strategy)
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
