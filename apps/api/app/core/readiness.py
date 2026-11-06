"""Dependency readiness probes for /health/ready (TRD §4.3, §12).

Each probe is independent, bounded by a timeout, and returns only non-secret status data.
"""

import logging
import time
from functools import lru_cache
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings

logger = logging.getLogger(__name__)

CheckState = Literal["ok", "unavailable", "missing"]


class DependencyCheck(BaseModel):
    name: str
    state: CheckState
    required: bool
    detail: str
    remediation: str | None = None
    latency_ms: float | None = None


class ReadinessProbe(Protocol):
    def __call__(self) -> list[DependencyCheck]: ...


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


_PG_VERSION_SQL = text(
    "SELECT current_setting('server_version'), "
    "(SELECT extversion FROM pg_extension WHERE extname = 'vector')"
)


def check_postgres(engine: Engine) -> list[DependencyCheck]:
    started = time.perf_counter()
    remediation = "Start the database: ./scripts/db.ps1 start (or docker compose, see README)"
    try:
        with engine.connect() as conn:
            row = conn.execute(_PG_VERSION_SQL).one_or_none()
    except SQLAlchemyError as exc:
        # Never echo the driver message: it can contain host/user details.
        logger.warning("postgres_unavailable", extra={"error_type": type(exc).__name__})
        return [
            DependencyCheck(
                name="postgres",
                state="unavailable",
                required=True,
                detail="Cannot connect to PostgreSQL.",
                remediation=remediation,
                latency_ms=_elapsed_ms(started),
            )
        ]
    server_version, vector_version = row if row else (None, None)
    checks = [
        DependencyCheck(
            name="postgres",
            state="ok",
            required=True,
            detail=f"PostgreSQL {server_version}",
            latency_ms=_elapsed_ms(started),
        )
    ]
    checks.append(
        DependencyCheck(
            name="pgvector",
            state="ok" if vector_version else "missing",
            required=True,
            detail=f"pgvector {vector_version}" if vector_version else "pgvector is not installed.",
            remediation=None if vector_version else "Run: CREATE EXTENSION vector;",
        )
    )
    return checks


@lru_cache(maxsize=4)
def _ollama_probe_client(base_url: str, timeout: float) -> httpx.Client:
    # Reused: building an httpx.Client loads the CA bundle (~200 ms on Windows) even for http://.
    return httpx.Client(base_url=base_url, timeout=timeout)


def check_ollama(settings: Settings, client: httpx.Client | None = None) -> list[DependencyCheck]:
    started = time.perf_counter()
    client = client or _ollama_probe_client(
        settings.ollama_base_url, settings.health_check_timeout_seconds
    )
    try:
        version = client.get("/api/version").raise_for_status().json().get("version")
        tags = client.get("/api/tags").raise_for_status().json().get("models", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ollama_unavailable", extra={"error_type": type(exc).__name__})
        return [
            DependencyCheck(
                name="ollama",
                state="unavailable",
                required=True,
                detail="Cannot reach the local Ollama runtime.",
                remediation="Install from https://ollama.com and start it (ollama serve).",
                latency_ms=_elapsed_ms(started),
            )
        ]
    installed = {str(m.get("name", "")) for m in tags if isinstance(m, dict)}
    checks = [
        DependencyCheck(
            name="ollama",
            state="ok",
            required=True,
            detail=f"Ollama {version}",
            latency_ms=_elapsed_ms(started),
        )
    ]
    for role, model in (
        ("generation_model", settings.ollama_generation_model),
        ("embedding_model", settings.ollama_embedding_model),
    ):
        present = model in installed
        checks.append(
            DependencyCheck(
                name=role,
                state="ok" if present else "missing",
                # The API serves without models; RAG features report their own setup state.
                required=False,
                detail=f"{model} is installed." if present else f"{model} is not installed.",
                remediation=None if present else f"ollama pull {model}",
            )
        )
    return checks
