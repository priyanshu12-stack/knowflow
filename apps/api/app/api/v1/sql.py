"""SQL Analyst endpoints (TRD §8). Secrets are write-only; execution is read-only."""

import uuid
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep, SettingsDep, WorkspaceDep
from app.core.errors import ErrorResponse
from app.modules.models.registry import chat_model
from app.modules.sql_assistant import service
from app.schemas.sql import (
    ConnectionIn,
    ConnectionOut,
    GlossaryTermIO,
    HistoryItem,
    SchemaOut,
    SqlAnswerOut,
    SqlQueryIn,
)

router = APIRouter(prefix="/sql", tags=["sql"])
_ERR: dict[int | str, dict[str, Any]] = {c: {"model": ErrorResponse} for c in (404, 409, 422, 503)}


@router.get("/connections", response_model=list[ConnectionOut])
def list_connections(
    session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> list[ConnectionOut]:
    return service.list_connections(session, settings, workspace.id)


@router.post("/connections/test", response_model=ConnectionOut, status_code=201, responses=_ERR)
def test_connection(
    body: ConnectionIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> ConnectionOut:
    """Connect, verify the role is read-only and save. The password is never returned."""
    return service.test_and_save(session, settings, workspace.id, body)


@router.delete(
    "/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERR
)
def delete_connection(
    connection_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> Response:
    service.delete_connection(session, workspace.id, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/schema/{connection_id}", response_model=SchemaOut, responses=_ERR)
def get_schema(
    connection_id: uuid.UUID, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> SchemaOut:
    """Allow-listed tables, columns, types, descriptions and the glossary. No data rows."""
    return service.schema(session, settings, workspace.id, connection_id)


@router.put(
    "/connections/{connection_id}/glossary", response_model=list[GlossaryTermIO], responses=_ERR
)
def put_glossary(
    connection_id: uuid.UUID,
    body: list[GlossaryTermIO],
    session: SessionDep,
    workspace: WorkspaceDep,
) -> list[GlossaryTermIO]:
    return service.save_glossary(session, workspace.id, connection_id, body)


@router.post("/query", response_model=SqlAnswerOut, responses=_ERR)
def query(
    body: SqlQueryIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> SqlAnswerOut:
    """Either a clarification (nothing executed) or validated read-only SQL with its result."""
    return service.ask(session, settings, workspace.id, body, chat_model(session, settings))


@router.get(
    "/connections/{connection_id}/history", response_model=list[HistoryItem], responses=_ERR
)
def history(
    connection_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep
) -> list[HistoryItem]:
    service.get_connection(session, workspace.id, connection_id)
    return service.history(session, workspace.id, connection_id)
