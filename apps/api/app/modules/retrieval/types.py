"""Shared retrieval types. Every retriever returns ranked `Candidate`s for the same chunk set."""

import uuid
from dataclasses import dataclass, field
from typing import Literal

ChunkStrategy = Literal["fixed", "recursive"]


@dataclass(frozen=True)
class Scope:
    """What a query may see. The workspace filter is applied inside every SQL query (SEC-03)."""

    workspace_id: uuid.UUID
    strategy: ChunkStrategy = "recursive"
    document_ids: tuple[uuid.UUID, ...] | None = None


@dataclass
class Candidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    text: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    chunk_index: int
    score: float
    # rank per retriever, 1-based, e.g. {"dense": 3, "lexical": 1}; kept for evaluation traces
    ranks: dict[str, int] = field(default_factory=dict)
