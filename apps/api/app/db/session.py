"""Shared SQLAlchemy engine. Sync engine + psycopg 3: endpoints are `def` and run in the threadpool.

psycopg's async mode doesn't support Windows' default Proactor event loop, and a single-user
local app gains nothing from async DB I/O. See docs/architecture/overview.md.
"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

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
