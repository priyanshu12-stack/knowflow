"""STK-05: real PostgreSQL + pgvector readiness. Runs only with KNOWFLOW_RUN_INTEGRATION=1."""

import pytest

from app.core.readiness import check_postgres
from app.db.session import get_engine

# Skipped unless KNOWFLOW_RUN_INTEGRATION=1 (see tests/conftest.py).
pytestmark = pytest.mark.integration


def test_postgres_and_pgvector_are_ready() -> None:
    checks = {c.name: c for c in check_postgres(get_engine())}
    assert checks["postgres"].state == "ok", checks["postgres"].detail
    assert checks["pgvector"].state == "ok", checks["pgvector"].detail
    assert checks["pgvector"].detail.startswith("pgvector 0.8")
