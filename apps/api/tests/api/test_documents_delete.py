"""ING-13: delete removes metadata, jobs and the stored file; idempotent."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import IngestionJob

pytestmark = pytest.mark.integration


def test_delete_removes_everything_and_is_idempotent(
    db_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    up = db_client.post(
        "/api/v1/documents", files={"file": ("gone.txt", b"to be deleted", "text/plain")}
    ).json()
    assert [p for p in storage_root.rglob("*") if p.is_file()]

    res = db_client.delete(f"/api/v1/documents/{up['document_id']}")
    assert res.status_code == 204
    assert res.content == b""
    assert [p for p in storage_root.rglob("*") if p.is_file()] == []
    assert db_client.get(f"/api/v1/documents/{up['document_id']}").status_code == 404
    assert db_client.get(f"/api/v1/jobs/{up['job_id']}").status_code == 404
    assert db_session.scalar(select(func.count()).select_from(IngestionJob)) == 0

    again = db_client.delete(f"/api/v1/documents/{up['document_id']}")
    assert again.status_code == 204


def test_delete_succeeds_when_file_is_already_missing(
    db_client: TestClient, storage_root: Path
) -> None:
    up = db_client.post(
        "/api/v1/documents", files={"file": ("lost.txt", b"file vanished", "text/plain")}
    ).json()
    for path in storage_root.rglob("*"):
        if path.is_file():
            path.unlink()
    assert db_client.delete(f"/api/v1/documents/{up['document_id']}").status_code == 204
    assert db_client.get("/api/v1/documents").json()["total"] == 0


def test_deleted_content_can_be_uploaded_again_without_duplicate_prompt(
    db_client: TestClient,
) -> None:
    files = {"file": ("again.txt", b"same bytes", "text/plain")}
    up = db_client.post("/api/v1/documents", files=files).json()
    db_client.delete(f"/api/v1/documents/{up['document_id']}")
    res = db_client.post("/api/v1/documents", files=files)
    assert res.status_code == 202
    assert res.json()["outcome"] == "created"
