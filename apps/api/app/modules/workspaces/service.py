"""Workspace resolution (WSP-02, CON-08). Local v1 is single-user: requests act in the default
workspace, which the first migration creates. Every content query is still scoped by its id."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Workspace


def get_default_workspace(session: Session) -> Workspace:
    workspace = session.scalar(select(Workspace).where(Workspace.is_default))
    if workspace is None:
        raise AppError(
            "workspace_not_initialized",
            "No workspace exists yet. Run the database migrations: ./scripts/dev.ps1 migrate",
            503,
        )
    return workspace


def rename_workspace(session: Session, workspace: Workspace, name: str) -> Workspace:
    workspace.name = name
    session.commit()
    session.refresh(workspace)
    return workspace
