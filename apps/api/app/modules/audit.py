"""Audit trail (TRD §7 audit_events, §11). Records ids, counts and statuses, never content.

`record` adds the event to the caller's session, so it commits (or rolls back) with the change it
describes. Metadata passes through the log redactor as a second line of defence.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import redact, request_id_var
from app.db.models import AuditEvent

_ALLOWED_TYPES = (str, int, float, bool, type(None))


def _safe(metadata: dict[str, Any]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, _ALLOWED_TYPES):
            # Short scalars only; long strings could be content, so they're truncated.
            out[key] = value[:120] if isinstance(value, str) else value
    return dict(redact(out))


def record(
    session: Session,
    *,
    workspace_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: object | None = None,
    actor: str = "local-user",
    **metadata: Any,
) -> None:
    session.add(
        AuditEvent(
            workspace_id=workspace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            request_id=request_id_var.get(),
            metadata_safe=_safe(metadata),
        )
    )


def audit_commit(
    session: Session,
    workspace_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: object | None = None,
    **metadata: Any,
) -> None:
    """Record an event for a change that has just been made, and commit it."""
    record(
        session,
        workspace_id=workspace_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        **metadata,
    )
    session.commit()
