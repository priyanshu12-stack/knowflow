"""CON-08 / SEC-03: documents and jobs in another workspace are invisible and untouchable."""

import hashlib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Document, IngestionJob, Workspace
from app.modules.documents.storage import FileStorage, make_storage_key

pytestmark = pytest.mark.integration

FOREIGN_CONTENT = b"Belongs to a different workspace."


@pytest.fixture
def foreign(db_session: Session, storage_root: Path) -> tuple[Document, IngestionJob, Path]:
    ws = Workspace(id=uuid.uuid4(), name="Other team")
    doc_id = uuid.uuid4()
    key = make_storage_key(ws.id, doc_id)
    doc = Document(
        id=doc_id,
        workspace_id=ws.id,
        original_name="private.txt",
        storage_key=key,
        file_type="txt",
        mime_type="text/plain",
        size_bytes=len(FOREIGN_CONTENT),
        sha256=hashlib.sha256(FOREIGN_CONTENT).hexdigest(),
        status="queued",
    )
    job = IngestionJob(id=uuid.uuid4(), document_id=doc_id, status="queued")
    db_session.add(ws)
    db_session.flush()  # no ORM relationship orders workspace before document
    db_session.add_all([doc, job])
    db_session.commit()
    path = FileStorage(storage_root).path_for(key)
    path.parent.mkdir(parents=True)
    path.write_bytes(FOREIGN_CONTENT)
    return doc, job, path


def test_foreign_documents_are_not_listed_or_readable(
    db_client: TestClient, foreign: tuple[Document, IngestionJob, Path]
) -> None:
    doc, job, _ = foreign
    assert db_client.get("/api/v1/documents").json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }
    assert db_client.get(f"/api/v1/documents/{doc.id}").status_code == 404
    assert db_client.get(f"/api/v1/jobs/{job.id}").status_code == 404


def test_foreign_document_cannot_be_deleted(
    db_client: TestClient, db_session: Session, foreign: tuple[Document, IngestionJob, Path]
) -> None:
    doc, _, path = foreign
    assert db_client.delete(f"/api/v1/documents/{doc.id}").status_code == 204
    db_session.expire_all()
    assert db_session.get(Document, doc.id) is not None
    assert path.read_bytes() == FOREIGN_CONTENT


def test_duplicate_detection_is_per_workspace(
    db_client: TestClient, foreign: tuple[Document, IngestionJob, Path]
) -> None:
    res = db_client.post(
        "/api/v1/documents", files={"file": ("mine.txt", FOREIGN_CONTENT, "text/plain")}
    )
    assert res.status_code == 202
    assert res.json()["outcome"] == "created"


def test_foreign_workspace_cannot_be_renamed(
    db_client: TestClient, foreign: tuple[Document, IngestionJob, Path]
) -> None:
    doc, _, _ = foreign
    res = db_client.patch(f"/api/v1/workspaces/{doc.workspace_id}", json={"name": "Hijacked"})
    assert res.status_code == 404
