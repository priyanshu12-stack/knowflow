"""STK-17: request correlation."""

import uuid

from fastapi.testclient import TestClient


def test_generates_uuid_when_absent(client: TestClient) -> None:
    rid = client.get("/api/v1/health/live").headers["X-Request-ID"]
    uuid.UUID(rid)


def test_accepts_safe_inbound_id(client: TestClient) -> None:
    res = client.get("/api/v1/health/live", headers={"X-Request-ID": "trace-abc_123.x"})
    assert res.headers["X-Request-ID"] == "trace-abc_123.x"


def test_rejects_unsafe_inbound_id(client: TestClient) -> None:
    res = client.get("/api/v1/health/live", headers={"X-Request-ID": 'bad"\\injected id'})
    assert res.headers["X-Request-ID"] != 'bad"\\injected id'
    uuid.UUID(res.headers["X-Request-ID"])
