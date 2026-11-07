"""Ask KnowFlow endpoints (TRD §8): grounded answers, conversations and feedback."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SessionDep, SettingsDep, WorkspaceDep
from app.core.errors import ErrorResponse
from app.modules.audit import audit_commit
from app.modules.models.registry import chat_model
from app.modules.rag import service
from app.schemas.chat import (
    AnswerOut,
    ChatQuery,
    ConversationDetail,
    ConversationOut,
    FeedbackIn,
    RenameConversation,
)
from app.schemas.common import Page, PageParams, page_params

router = APIRouter(tags=["chat"])

_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (404, 409, 422, 429, 502, 503)
}


@router.post("/chat/query", response_model=AnswerOut, responses=_ERRORS)
def chat_query(
    body: ChatQuery, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> AnswerOut:
    """Answer from retrieved evidence with verified citations, or abstain. Not streamed (v1)."""
    answer = service.ask(session, settings, workspace.id, body, chat_model(session, settings))
    audit_commit(
        session,
        workspace.id,
        "chat.answered",
        "message",
        answer.message_id,
        abstained=answer.abstained,
        citations=len(answer.citations),
        mode=answer.retrieval.mode,
        latency_ms=answer.latency_ms,
        model=answer.model,
    )
    return answer


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    session: SessionDep,
    workspace: WorkspaceDep,
    page: Annotated[PageParams, Depends(page_params)],
) -> Page[ConversationOut]:
    items, total = service.list_conversations(
        session, workspace.id, limit=page.limit, offset=page.offset
    )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    responses={404: {"model": ErrorResponse}},
)
def get_conversation(
    conversation_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> ConversationDetail:
    conversation = service.get_conversation(session, workspace.id, conversation_id)
    return service.conversation_detail(session, conversation)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    responses={404: {"model": ErrorResponse}},
)
def rename_conversation(
    conversation_id: uuid.UUID,
    body: RenameConversation,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> ConversationDetail:
    conversation = service.get_conversation(session, workspace.id, conversation_id)
    conversation.title = body.title
    audit_commit(session, workspace.id, "conversation.renamed", "conversation", conversation.id)
    return service.conversation_detail(session, conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> Response:
    """Idempotent; deletes messages and feedback with it."""
    from app.core.errors import AppError

    try:
        conversation = service.get_conversation(session, workspace.id, conversation_id)
    except AppError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    session.delete(conversation)
    audit_commit(session, workspace.id, "conversation.deleted", "conversation", conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/messages/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def put_feedback(
    message_id: uuid.UUID, body: FeedbackIn, session: SessionDep, workspace: WorkspaceDep
) -> Response:
    service.set_feedback(session, workspace.id, message_id, body.rating, body.reason)
    audit_commit(
        session,
        workspace.id,
        "feedback.recorded",
        "message",
        message_id,
        rating=body.rating,
        has_reason=bool(body.reason),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
