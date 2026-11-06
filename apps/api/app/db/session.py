"""Shared SQLAlchemy engine and request sessions. Sync engine + psycopg 3: endpoints are `def` and
run in the threadpool.

psycopg's async mode doesn't support Windows' default Proactor event loop, and a single-user
local app gains nothing from async DB I/O. See docs/architecture/overview.md.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=settings.health_check_timeout_seconds,
        connect_args={"connect_timeout": max(1, int(settings.health_check_timeout_seconds))},
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed (rolled back if uncommitted)."""
    with _session_factory()() as session:
        yield session
