"""Workspace endpoints (WSP-02): read and rename the local default workspace."""

import uuid

from fastapi import APIRouter

from app.api.deps import SessionDep, WorkspaceDep
from app.core.errors import AppError, ErrorResponse
from app.modules.workspaces.service import rename_workspace
from app.schemas.workspaces import WorkspaceOut, WorkspaceUpdate

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/current", response_model=WorkspaceOut)
def get_current_workspace(workspace: WorkspaceDep) -> WorkspaceOut:
    return WorkspaceOut.model_validate(workspace)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    responses={404: {"model": ErrorResponse}},
)
def update_workspace(
    workspace_id: uuid.UUID, body: WorkspaceUpdate, session: SessionDep, workspace: WorkspaceDep
) -> WorkspaceOut:
    if workspace_id != workspace.id:
        raise AppError("workspace_not_found", "This workspace doesn't exist.", 404)
    return WorkspaceOut.model_validate(rename_workspace(session, workspace, body.name))
