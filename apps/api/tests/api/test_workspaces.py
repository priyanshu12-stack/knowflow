"""WSP-02: default local workspace exists without registration and can be renamed."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_current_workspace_is_the_seeded_default(db_client: TestClient) -> None:
    res = db_client.get("/api/v1/workspaces/current")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "My workspace"
    assert body["is_default"] is True


def test_rename_trims_and_persists(db_client: TestClient) -> None:
    ws = db_client.get("/api/v1/workspaces/current").json()
    res = db_client.patch(f"/api/v1/workspaces/{ws['id']}", json={"name": "  Research lab  "})
    assert res.status_code == 200
    assert res.json()["name"] == "Research lab"
    assert db_client.get("/api/v1/workspaces/current").json()["name"] == "Research lab"


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "   "}, {"name": "x" * 81}, {}])
def test_invalid_names_are_rejected(db_client: TestClient, body: dict[str, str]) -> None:
    ws = db_client.get("/api/v1/workspaces/current").json()
    res = db_client.patch(f"/api/v1/workspaces/{ws['id']}", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_unknown_fields_are_rejected(db_client: TestClient) -> None:
    ws = db_client.get("/api/v1/workspaces/current").json()
    res = db_client.patch(
        f"/api/v1/workspaces/{ws['id']}", json={"name": "Ok", "is_default": False}
    )
    assert res.status_code == 422


def test_unknown_workspace_is_404(db_client: TestClient) -> None:
    res = db_client.patch(
        "/api/v1/workspaces/00000000-0000-4000-8000-000000000000", json={"name": "Nope"}
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "workspace_not_found"
