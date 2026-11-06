"""API-03, API-04, REL-06: liveness and readiness contracts."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.health import get_readiness_probes
from app.core.readiness import DependencyCheck


def _check(name: str, state: str, required: bool = True) -> DependencyCheck:
    return DependencyCheck(name=name, state=state, required=required, detail=f"{name} {state}")  # type: ignore[arg-type]


def _override(app: FastAPI, *checks: DependencyCheck) -> None:
    app.dependency_overrides[get_readiness_probes] = lambda: [lambda: list(checks)]


def test_live_returns_ok(client: TestClient) -> None:
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers["X-Request-ID"]


def test_ready_when_all_dependencies_ok(app: FastAPI, client: TestClient) -> None:
    _override(app, _check("postgres", "ok"), _check("ollama", "ok"))
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_ready_degraded_when_optional_model_missing(app: FastAPI, client: TestClient) -> None:
    _override(
        app,
        _check("postgres", "ok"),
        _check("ollama", "ok"),
        _check("embedding_model", "missing", required=False),
    )
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "degraded"


def test_ready_503_when_required_dependency_down(app: FastAPI, client: TestClient) -> None:
    _override(app, _check("postgres", "unavailable"), _check("ollama", "ok"))
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "not_ready"
    # Each dependency is reported separately.
    assert {c["name"]: c["state"] for c in body["checks"]} == {
        "postgres": "unavailable",
        "ollama": "ok",
    }
