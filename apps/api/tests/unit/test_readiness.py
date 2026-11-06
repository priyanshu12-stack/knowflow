"""MOD-01: Ollama probe behaviour, using a fake transport (no network)."""

import httpx
from sqlalchemy import create_engine

from app.core.config import Settings
from app.core.readiness import check_ollama, check_postgres

SETTINGS = Settings(
    _env_file=None,  # type: ignore[call-arg]
    ollama_generation_model="qwen3:4b",
    ollama_embedding_model="nomic-embed-text:v1.5",
)


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(base_url="http://ollama.test", transport=handler)


def test_ollama_ok_with_models_installed() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.17.1"})
        return httpx.Response(
            200, json={"models": [{"name": "qwen3:4b"}, {"name": "nomic-embed-text:v1.5"}]}
        )

    checks = {c.name: c for c in check_ollama(SETTINGS, _client(httpx.MockTransport(handler)))}
    assert checks["ollama"].state == "ok"
    assert checks["ollama"].detail == "Ollama 0.17.1"
    assert checks["generation_model"].state == "ok"
    assert checks["embedding_model"].state == "ok"


def test_missing_models_report_exact_pull_command() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.17.1"})
        return httpx.Response(200, json={"models": []})

    checks = {c.name: c for c in check_ollama(SETTINGS, _client(httpx.MockTransport(handler)))}
    assert checks["generation_model"].state == "missing"
    assert checks["generation_model"].required is False
    assert checks["generation_model"].remediation == "ollama pull qwen3:4b"
    assert checks["embedding_model"].remediation == "ollama pull nomic-embed-text:v1.5"


def test_ollama_unreachable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    checks = check_ollama(SETTINGS, _client(httpx.MockTransport(handler)))
    assert len(checks) == 1
    assert checks[0].state == "unavailable"
    assert checks[0].required is True
    assert checks[0].remediation


def test_postgres_unreachable_does_not_leak_connection_details() -> None:
    engine = create_engine(
        "postgresql+psycopg://leaky_user:leaky_pw@127.0.0.1:1/nodb",
        connect_args={"connect_timeout": 1},
    )
    checks = check_postgres(engine)
    assert checks[0].state == "unavailable"
    dumped = checks[0].model_dump_json()
    assert "leaky" not in dumped
    assert "127.0.0.1" not in dumped
