"""Request-scoped dependencies. Tests override `get_session` and `get_storage`."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Workspace
from app.db.session import get_session
from app.modules.documents.storage import FileStorage
from app.modules.workspaces.service import get_default_workspace


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> FileStorage:
    return FileStorage(settings.storage_root)


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[FileStorage, Depends(get_storage)]


def current_workspace(session: SessionDep) -> Workspace:
    return get_default_workspace(session)


WorkspaceDep = Annotated[Workspace, Depends(current_workspace)]
