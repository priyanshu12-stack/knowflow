"""STK-20 / WSP-02: Alembic owns the schema; models and migrations never drift apart."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.readiness import check_schema
from app.db.base import Base
from app.db.migrations import current_heads, expected_heads
from app.db.models import Document, Workspace
from tests.conftest import run_migrations

pytestmark = pytest.mark.integration


def test_database_is_at_head(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        assert current_heads(conn) == expected_heads()
    assert [c.state for c in check_schema(db_engine)] == ["ok"]


def test_models_match_migrations(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_round_trip(db_engine: Engine) -> None:
    run_migrations(db_engine, "base", downgrade=True)
    try:
        with db_engine.connect() as conn:
            assert conn.scalar(text("SELECT to_regclass('public.documents')")) is None
        schema = check_schema(db_engine)
        assert schema[0].state == "missing"
        assert schema[0].remediation == "./scripts/dev.ps1 migrate"
    finally:
        run_migrations(db_engine)
    assert check_schema(db_engine)[0].state == "ok"


def test_exactly_one_default_workspace_is_seeded(db_session: Session) -> None:
    defaults = db_session.scalars(select(Workspace).where(Workspace.is_default)).all()
    assert len(defaults) == 1
    assert defaults[0].name == "My workspace"


def test_second_default_workspace_is_rejected(db_session: Session) -> None:
    db_session.add(Workspace(name="Another", is_default=True))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def _document(workspace_id: uuid.UUID, **overrides: object) -> Document:
    doc_id = uuid.uuid4()
    values: dict[str, object] = {
        "id": doc_id,
        "workspace_id": workspace_id,
        "original_name": "a.txt",
        "storage_key": f"{workspace_id}/{doc_id}",
        "file_type": "txt",
        "mime_type": "text/plain",
        "size_bytes": 10,
        "sha256": "a" * 64,
        "version": 1,
        "status": "queued",
    }
    values.update(overrides)
    return Document(**values)


def _default_id(session: Session) -> uuid.UUID:
    return session.scalars(select(Workspace.id).where(Workspace.is_default)).one()


def test_same_checksum_and_version_is_rejected(db_session: Session) -> None:
    ws = _default_id(db_session)
    db_session.add(_document(ws))
    db_session.commit()
    db_session.add(_document(ws))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(_document(ws, version=2))
    db_session.commit()
    count = db_session.scalar(select(func.count()).select_from(Document))
    assert count == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "done"},
        {"file_type": "exe"},
        {"sha256": "not-a-hash"},
        {"size_bytes": 0},
        {"version": 0},
    ],
)
def test_check_constraints(db_session: Session, overrides: dict[str, object]) -> None:
    db_session.add(_document(_default_id(db_session), **overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
