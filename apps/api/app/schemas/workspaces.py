"""Workspace API contracts (WSP-02)."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

WorkspaceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: WorkspaceName
