"""Alembic helpers shared by readiness checks and tests."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

API_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


@lru_cache
def expected_heads() -> frozenset[str]:
    """Revisions this code expects the database to be at."""
    return frozenset(ScriptDirectory.from_config(alembic_config()).get_heads())


def current_heads(connection: Connection) -> frozenset[str]:
    return frozenset(MigrationContext.configure(connection).get_current_heads())
