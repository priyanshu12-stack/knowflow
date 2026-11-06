import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# API tests override external probes via DI; only `integration` tests touch a real database.
os.environ.setdefault("APP_ENV", "test")

from app.api.deps import get_storage
from app.core.config import get_settings
from app.db.migrations import alembic_config
from app.db.session import get_session
from app.main import create_app
from app.modules.documents.storage import FileStorage

if TYPE_CHECKING:
    from tests.fake_ollama import FakeOllama

RUN_INTEGRATION = os.environ.get("KNOWFLOW_RUN_INTEGRATION") == "1"
# Real local models (needs Ollama with the pinned models pulled). Never set in CI.
RUN_OLLAMA = os.environ.get("KNOWFLOW_RUN_OLLAMA") == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_db = pytest.mark.skip(reason="set KNOWFLOW_RUN_INTEGRATION=1 with a running database")
    skip_models = pytest.mark.skip(reason="set KNOWFLOW_RUN_OLLAMA=1 with local models pulled")
    for item in items:
        if "integration" in item.keywords and not RUN_INTEGRATION:
            item.add_marker(skip_db)
        if "ollama" in item.keywords and not RUN_OLLAMA:
            item.add_marker(skip_models)


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- Integration fixtures: a throwaway `<POSTGRES_DB>_test` database, migrated by Alembic. ---


def run_migrations(engine: Engine, revision: str = "head", *, downgrade: bool = False) -> None:
    with engine.begin() as conn:
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        cfg.attributes["configure_logger"] = False
        (command.downgrade if downgrade else command.upgrade)(cfg, revision)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    settings = get_settings()
    test_db = f"{settings.postgres_db}_test"
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", test_db):
        raise RuntimeError("POSTGRES_DB must be a plain identifier for the test database name")
    admin = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    drop = text(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)')
    with admin.connect() as conn:
        conn.execute(drop)
        conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    engine = create_engine(settings.database_url.set(database=test_db))
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    run_migrations(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(drop)
        admin.dispose()


def _reset(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE ingestion_jobs, documents, worker_heartbeats, embedding_versions, "
                "model_settings, conversations, evaluation_datasets, sql_connections CASCADE"
            )
        )
        conn.execute(text("DELETE FROM workspaces WHERE NOT is_default"))
        conn.execute(text("UPDATE workspaces SET name = 'My workspace'"))


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine, expire_on_commit=False) as session:
        yield session
    _reset(db_engine)


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture
def db_client(
    app: FastAPI, db_engine: Engine, db_session: Session, storage_root: Path
) -> Iterator[TestClient]:
    """API client backed by the test database and a temporary storage root."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    def _session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_storage] = lambda: FileStorage(storage_root)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_ollama(monkeypatch: pytest.MonkeyPatch) -> "FakeOllama":
    """Route every Ollama call in the app to an in-memory fake."""
    from app.modules.models import registry
    from app.modules.models import service as model_service
    from app.modules.models.ollama import OllamaClient
    from tests.fake_ollama import FakeOllama

    fake = FakeOllama()

    def make(base_url: str, timeout: float) -> OllamaClient:
        return OllamaClient(base_url, timeout=timeout, transport=fake.transport())

    monkeypatch.setattr(registry, "ollama_client", make)
    monkeypatch.setattr(model_service, "ollama_client", make)
    return fake
