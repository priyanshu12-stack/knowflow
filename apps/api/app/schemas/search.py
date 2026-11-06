"""Search API contracts."""

import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.documents import ChunkStrategy


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    text: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    score: float
    ranks: dict[str, int]


class SearchResponse(BaseModel):
    query: str
    mode: Literal["lexical", "dense", "hybrid"]
    strategy: ChunkStrategy
    hits: list[SearchHit]
