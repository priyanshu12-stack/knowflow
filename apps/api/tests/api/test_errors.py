"""API-02: stable error envelope with request_id and no stack traces."""

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.errors import AppError


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    err = res.json()["error"]
    assert err["code"] == "not_found"
    assert err["request_id"] == res.headers["X-Request-ID"]


def test_app_error_is_returned_verbatim(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom-app")
    def boom_app() -> None:
        raise AppError("document_not_found", "That document does not exist.", 404)

    res = client.get("/boom-app")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "document_not_found"
    assert res.json()["error"]["message"] == "That document does not exist."


def test_unhandled_error_hides_internals(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret connection string postgres://user:pw@host")

    res = client.get("/boom")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert "secret" not in res.text
    assert "Traceback" not in res.text


def test_validation_error_lists_fields_without_input_values(
    app: FastAPI, client: TestClient
) -> None:
    @app.get("/needs-int")
    def needs_int(n: int = Query()) -> int:
        return n

    res = client.get("/needs-int", params={"n": "private-value"})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert err["fields"][0]["loc"] == ["query", "n"]
    assert "private-value" not in res.text


class _FakeDriverError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("driver detail with host=db.internal user=knowflow")
        self.sqlstate = sqlstate


def test_missing_table_maps_to_schema_not_migrated(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom-schema")
    def boom_schema() -> None:
        raise ProgrammingError("SELECT 1", {}, _FakeDriverError("42P01"))

    res = client.get("/boom-schema")
    assert res.status_code == 503
    err = res.json()["error"]
    assert err["code"] == "schema_not_migrated"
    assert "./scripts/dev.ps1 migrate" in err["message"]
    assert "db.internal" not in res.text


def test_connection_failure_maps_to_database_unavailable(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom-db")
    def boom_db() -> None:
        raise OperationalError("SELECT 1", {}, _FakeDriverError("08006"))

    res = client.get("/boom-db")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "database_unavailable"
    assert "db.internal" not in res.text


def test_other_database_errors_stay_internal(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom-other")
    def boom_other() -> None:
        raise ProgrammingError("SELECT 1", {}, _FakeDriverError("42601"))

    res = client.get("/boom-other")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"


def test_app_error_details_are_included(app: FastAPI, client: TestClient) -> None:
    @app.get("/boom-details")
    def boom_details() -> None:
        raise AppError("duplicate_document", "Exists.", 409, details={"choices": ["skip"]})

    res = client.get("/boom-details")
    assert res.json()["error"]["details"] == {"choices": ["skip"]}
