"""Liveness and readiness endpoints (TRD §8)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.readiness import (
    DependencyCheck,
    ReadinessProbe,
    check_ollama,
    check_postgres,
    check_schema,
    check_worker,
)
from app.db.session import get_engine

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    # ready: everything ok · degraded: optional items missing · not_ready: a required item failed
    status: Literal["ready", "degraded", "not_ready"]
    checks: list[DependencyCheck]


def get_readiness_probes(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ReadinessProbe]:
    return [
        lambda: check_postgres(get_engine()),
        lambda: check_schema(get_engine()),
        lambda: check_ollama(settings),
        lambda: check_worker(get_engine(), settings),
    ]


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "A required dependency is down"}},
)
def ready(
    response: Response,
    probes: Annotated[list[ReadinessProbe], Depends(get_readiness_probes)],
) -> ReadyResponse:
    checks = [check for probe in probes for check in probe()]
    if any(c.required and c.state != "ok" for c in checks):
        overall: Literal["ready", "degraded", "not_ready"] = "not_ready"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c.state != "ok" for c in checks):
        overall = "degraded"
    else:
        overall = "ready"
    return ReadyResponse(status=overall, checks=checks)
