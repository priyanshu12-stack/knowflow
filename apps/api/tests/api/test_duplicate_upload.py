"""ING-12: identical SHA-256 content -> explicit skip / re-index / new-version choice."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Document, IngestionJob

pytestmark = pytest.mark.integration

CONTENT = b"Identical content for duplicate detection.\n"


def _upload(client: TestClient, name: str = "original.txt", **params: str) -> Response:
    return client.post(
        "/api/v1/documents", files={"file": (name, CONTENT, "text/plain")}, params=params
    )


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def test_duplicate_without_choice_returns_409_with_existing_document(
    db_client: TestClient, storage_root: Path
) -> None:
    first = _upload(db_client).json()
    res = _upload(db_client, "renamed copy.txt")
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "duplicate_document"
    assert "original.txt" in err["message"]
    assert err["details"]["existing_document"]["id"] == first["document_id"]
    assert err["details"]["choices"] == ["skip", "reindex", "new_version"]
    assert len(_files(storage_root)) == 1
    assert db_client.get("/api/v1/documents").json()["total"] == 1


def test_skip_returns_existing_document_without_changes(
    db_client: TestClient, storage_root: Path
) -> None:
    first = _upload(db_client).json()
    res = _upload(db_client, on_duplicate="skip")
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "skipped"
    assert body["document_id"] == first["document_id"]
    assert body["job_id"] is None
    assert len(_files(storage_root)) == 1
    assert db_client.get("/api/v1/documents").json()["total"] == 1


def test_reindex_reuses_an_active_job(db_client: TestClient) -> None:
    first = _upload(db_client).json()
    res = _upload(db_client, on_duplicate="reindex")
    assert res.status_code == 202
    body = res.json()
    assert body["outcome"] == "reindexed"
    assert body["document_id"] == first["document_id"]
    assert body["job_id"] == first["job_id"]  # idempotent: no second queued job


def test_reindex_after_failure_queues_a_new_job(db_client: TestClient, db_session: Session) -> None:
    first = _upload(db_client).json()
    db_session.execute(
        update(IngestionJob)
        .where(IngestionJob.id == first["job_id"])
        .values(status="failed", error_code="extraction_failed", error_message_safe="Bad PDF.")
    )
    db_session.execute(
        update(Document).where(Document.id == first["document_id"]).values(status="failed")
    )
    db_session.commit()
    failed = db_client.get(f"/api/v1/documents/{first['document_id']}").json()
    assert failed["last_error"] == {"code": "extraction_failed", "message": "Bad PDF."}

    res = _upload(db_client, on_duplicate="reindex")
    assert res.status_code == 202
    body = res.json()
    assert body["job_id"] != first["job_id"]
    assert body["status"] == "queued"
    assert body["document"]["last_error"] is None


def test_new_version_creates_a_separate_document(db_client: TestClient, storage_root: Path) -> None:
    first = _upload(db_client).json()
    res = _upload(db_client, "original v2.txt", on_duplicate="new_version")
    assert res.status_code == 202
    body = res.json()
    assert body["outcome"] == "new_version"
    assert body["document_id"] != first["document_id"]
    assert body["document"]["version"] == 2
    assert body["document"]["sha256"] == first["document"]["sha256"]
    assert len(_files(storage_root)) == 2
    third = _upload(db_client, on_duplicate="new_version").json()
    assert third["document"]["version"] == 3


def test_choice_is_ignored_when_content_is_new(db_client: TestClient) -> None:
    res = _upload(db_client, on_duplicate="skip")
    assert res.status_code == 202
    assert res.json()["outcome"] == "created"


def test_invalid_choice_is_rejected(db_client: TestClient) -> None:
    res = _upload(db_client, on_duplicate="overwrite")
    assert res.status_code == 422
