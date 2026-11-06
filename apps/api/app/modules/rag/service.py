"""Ask KnowFlow use case: validate scope -> retrieve -> answer -> persist the turn (TRD §6.2).

Logs carry ids, counts, timings and the model; never the question or document text (TRD §11).
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import request_id_var
from app.db.models import Conversation, Document, Message, MessageFeedback
from app.modules.models.interfaces import ChatModel, ModelError
from app.modules.rag.answer import GroundedAnswer, answer_question
from app.modules.retrieval.service import RetrievalConfig, RetrievalResult, retrieve
from app.modules.retrieval.types import Scope
from app.schemas.chat import (
    AnswerOut,
    ChatQuery,
    CitationOut,
    ConversationDetail,
    ConversationOut,
    FeedbackOut,
    MessageOut,
    RetrievalTrace,
)

logger = logging.getLogger(__name__)

EXCERPT_CHARS = 1200

_gate_lock = threading.Lock()
_gate: threading.BoundedSemaphore | None = None


def _generation_gate(settings: Settings) -> threading.BoundedSemaphore:
    global _gate
    with _gate_lock:
        if _gate is None:
            _gate = threading.BoundedSemaphore(settings.max_concurrent_generations)
        return _gate


Retriever = Callable[[Session, Settings, str, RetrievalConfig, Scope], RetrievalResult]


def _title(question: str) -> str:
    title = " ".join(question.split())
    return title if len(title) <= 80 else title[:77].rstrip() + "…"


def _validate_documents(session: Session, workspace_id: uuid.UUID, ids: list[uuid.UUID]) -> None:
    found = session.scalars(
        select(Document.id).where(
            Document.workspace_id == workspace_id,
            Document.id.in_(ids),
            Document.status == "ready",
        )
    ).all()
    if len(set(found)) != len(set(ids)):
        raise AppError(
            "invalid_document_scope",
            "Some selected documents don't exist or aren't ready yet. Refresh and pick again.",
            422,
        )


def citation_out(c: Any) -> CitationOut:
    cand = c.candidate
    text = cand.text
    return CitationOut(
        number=c.number,
        chunk_id=cand.chunk_id,
        document_id=cand.document_id,
        document_name=cand.document_name,
        page_start=cand.page_start,
        page_end=cand.page_end,
        section_path=cand.section_path,
        excerpt=text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS].rstrip() + " …",
    )


def ask(
    session: Session,
    settings: Settings,
    workspace_id: uuid.UUID,
    query: ChatQuery,
    chat: ChatModel,
    *,
    retriever: Retriever = retrieve,
) -> AnswerOut:
    started = time.perf_counter()
    conversation: Conversation | None = None
    if query.conversation_id is not None:
        conversation = session.scalar(
            select(Conversation).where(
                Conversation.id == query.conversation_id,
                Conversation.workspace_id == workspace_id,
            )
        )
        if conversation is None:
            raise AppError("conversation_not_found", "This conversation doesn't exist.", 404)
    if query.document_ids:
        _validate_documents(session, workspace_id, query.document_ids)

    cfg = query.retrieval_config
    config = RetrievalConfig(
        mode=cfg.mode,
        strategy=cfg.strategy,
        top_k=cfg.top_k,
        candidates=settings.rag_candidates,
        rerank=cfg.rerank,
        rrf_k=settings.rrf_k,
    )
    scope = Scope(
        workspace_id=workspace_id,
        strategy=cfg.strategy,
        document_ids=tuple(query.document_ids) if query.document_ids else None,
    )
    result = retriever(session, settings, query.question, config, scope)

    gate = _generation_gate(settings)
    if not gate.acquire(timeout=settings.generation_queue_wait_seconds):
        raise AppError(
            "generation_busy",
            "Another answer is being generated on this machine. Try again in a moment.",
            429,
        )
    try:
        grounded: GroundedAnswer = answer_question(
            query.question,
            result.candidates,
            chat,
            max_context_chars=settings.rag_context_chars,
            # The similarity threshold only applies to cosine scores (dense mode).
            min_score=settings.rag_min_dense_score
            if result.mode == "dense" and settings.rag_min_dense_score >= 0
            else None,
            temperature=settings.rag_temperature,
        )
    except ModelError as exc:
        raise AppError(exc.code, exc.message, 503 if exc.retryable else 502) from exc
    finally:
        gate.release()

    latency = round((time.perf_counter() - started) * 1000)
    timings = dict(result.timings_ms)
    if grounded.generation_ms is not None:
        timings["generation"] = grounded.generation_ms
    trace = RetrievalTrace(
        mode=result.mode,
        strategy=result.strategy,
        top_k=cfg.top_k,
        candidates=len(result.candidates),
        sources_supplied=grounded.sources_supplied,
        reranked=result.reranked,
        timings_ms=timings,
        candidate_ranks=[
            {"chunk_id": str(c.chunk_id), "ranks": c.ranks, "score": round(c.score, 4)}
            for c in result.candidates
        ],
    )
    citations = [citation_out(c) for c in grounded.citations]

    if conversation is None:
        conversation = Conversation(
            id=uuid.uuid4(), workspace_id=workspace_id, title=_title(query.question)
        )
        session.add(conversation)
        session.flush()
    session.add(Message(conversation_id=conversation.id, role="user", content=query.question))
    session.flush()
    metadata: dict[str, object] = {
        "abstained": grounded.abstained,
        "abstain_reason": grounded.abstain_reason,
        "retrieval": trace.model_dump(mode="json"),
        "model": grounded.model,
        "prompt_version": grounded.prompt_version,
        "latency_ms": latency,
        "tokens": grounded.tokens,
        "document_ids": [str(d) for d in query.document_ids or []],
    }
    assistant = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=grounded.text,
        citations=[c.model_dump(mode="json") for c in citations],
        metadata_=metadata,
    )
    session.add(assistant)
    conversation.updated_at = func.now()
    session.commit()

    logger.info(
        "chat_answered",
        extra={
            "conversation_id": str(conversation.id),
            "message_id": str(assistant.id),
            "abstained": grounded.abstained,
            "abstain_reason": grounded.abstain_reason,
            "citations": len(citations),
            "candidates": len(result.candidates),
            "mode": result.mode,
            "model": grounded.model,
            "latency_ms": latency,
            "question_chars": len(query.question),
        },
    )
    return AnswerOut(
        conversation_id=conversation.id,
        message_id=assistant.id,
        answer=grounded.text,
        citations=citations,
        abstained=grounded.abstained,
        abstain_reason=grounded.abstain_reason,
        retrieval=trace,
        model=grounded.model,
        prompt_version=grounded.prompt_version,
        latency_ms=latency,
        request_id=request_id_var.get(),
    )


# --- Conversations ---


def list_conversations(
    session: Session, workspace_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[ConversationOut], int]:
    total = session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.workspace_id == workspace_id)
    )
    counts = (
        select(Message.conversation_id, func.count().label("n"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = session.execute(
        select(Conversation, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.conversation_id == Conversation.id)
        .where(Conversation.workspace_id == workspace_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=n,
        )
        for c, n in rows
    ], total or 0


def get_conversation(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> Conversation:
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.id == cid, Conversation.workspace_id == workspace_id
        )
    )
    if conversation is None:
        raise AppError("conversation_not_found", "This conversation doesn't exist.", 404)
    return conversation


def conversation_detail(session: Session, conversation: Conversation) -> ConversationDetail:
    messages = conversation.messages
    feedback = {
        f.message_id: f
        for f in session.scalars(
            select(MessageFeedback).where(MessageFeedback.message_id.in_([m.id for m in messages]))
        )
    }
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[CitationOut.model_validate(c) for c in m.citations],
                metadata=m.metadata_,
                feedback=FeedbackOut(rating=f.rating, reason=f.reason)
                if (f := feedback.get(m.id))
                else None,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


def set_feedback(
    session: Session,
    workspace_id: uuid.UUID,
    message_id: uuid.UUID,
    rating: str,
    reason: str | None,
) -> None:
    message = session.scalar(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == message_id,
            Message.role == "assistant",
            Conversation.workspace_id == workspace_id,
        )
    )
    if message is None:
        raise AppError("message_not_found", "This answer doesn't exist.", 404)
    existing = session.get(MessageFeedback, message_id)
    if existing is None:
        session.add(MessageFeedback(message_id=message_id, rating=rating, reason=reason))
    else:
        existing.rating, existing.reason = rating, reason
    session.commit()
    logger.info("feedback_recorded", extra={"message_id": str(message_id), "rating": rating})
