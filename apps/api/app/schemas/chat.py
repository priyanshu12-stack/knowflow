"""Ask KnowFlow API contracts (TRD §8: /chat/query, /conversations)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.documents import ChunkStrategy


class RetrievalConfigIn(BaseModel):
    mode: Literal["dense", "lexical"] = "dense"
    strategy: ChunkStrategy = "recursive"
    top_k: int = Field(default=6, ge=1, le=20)


class ChatQuery(BaseModel):
    conversation_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    retrieval_config: RetrievalConfigIn = Field(default_factory=RetrievalConfigIn)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class CitationOut(BaseModel):
    number: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    excerpt: str


class RetrievalTrace(BaseModel):
    mode: str
    strategy: str
    top_k: int
    candidates: int
    sources_supplied: int
    timings_ms: dict[str, int]
    # (chunk id, per-retriever ranks) for every candidate considered; used by error analysis.
    candidate_ranks: list[dict[str, object]] = Field(default_factory=list)


class AnswerOut(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    citations: list[CitationOut]
    abstained: bool
    abstain_reason: str | None
    retrieval: RetrievalTrace
    model: str | None
    prompt_version: str
    latency_ms: int
    request_id: str | None


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class FeedbackOut(BaseModel):
    rating: Literal["helpful", "not_helpful"]
    reason: str | None


class MessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[CitationOut]
    metadata: dict[str, object]
    feedback: FeedbackOut | None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class RenameConversation(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()


class FeedbackIn(BaseModel):
    rating: Literal["helpful", "not_helpful"]
    reason: str | None = Field(default=None, max_length=1000)
