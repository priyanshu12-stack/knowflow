"""ING-01..05, API-05, SEC-01: upload validation, safe storage, 202 + queued job, listing."""

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import Settings, get_settings
from app.main import create_app
from tests.files import DOCX_MIME, PDF_MIME, docx_bytes, pdf_bytes

pytestmark = pytest.mark.integration


def _upload(client: TestClient, name: str, data: bytes, mime: str, **params: str) -> Response:
    return client.post("/api/v1/documents", files={"file": (name, data, mime)}, params=params)


def _stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


@pytest.mark.parametrize(
    ("name", "data", "mime", "file_type"),
    [
        ("Quarterly report.pdf", pdf_bytes(), PDF_MIME, "pdf"),
        ("Policy.docx", docx_bytes(), DOCX_MIME, "docx"),
        ("notes.txt", b"Plain text notes\n", "text/plain", "txt"),
        ("README.md", b"# Heading\n\nBody\n", "application/octet-stream", "md"),
    ],
)
def test_upload_accepted_and_queued(
    db_client: TestClient,
    storage_root: Path,
    name: str,
    data: bytes,
    mime: str,
    file_type: str,
) -> None:
    res = _upload(db_client, name, data, mime)
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["outcome"] == "created"
    assert body["status"] == "queued"
    doc = body["document"]
    assert doc["original_name"] == name
    assert doc["file_type"] == file_type
    assert doc["size_bytes"] == len(data)
    assert doc["sha256"] == hashlib.sha256(data).hexdigest()
    assert doc["version"] == 1
    assert doc["page_count"] is None
    assert doc["chunk_count"] is None
    assert doc["last_error"] is None
    assert doc["latest_job"]["id"] == body["job_id"]

    # Stored under a generated key, never the original filename.
    files = _stored_files(storage_root)
    assert len(files) == 1
    assert files[0].read_bytes() == data
    assert files[0].name == body["document_id"]
    assert name not in str(files[0])

    job = db_client.get(f"/api/v1/jobs/{body['job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] == "queued"
    assert job.json()["stage"] is None
    assert job.json()["attempts"] == 0

    detail = db_client.get(f"/api/v1/documents/{body['document_id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == body["document_id"]


def test_canonical_mime_is_stored_not_the_declared_one(db_client: TestClient) -> None:
    res = _upload(db_client, "README.md", b"# Title\n", "application/octet-stream")
    assert res.json()["document"]["mime_type"] == "text/markdown"


def test_traversal_filename_is_reduced_to_display_name(
    db_client: TestClient, storage_root: Path
) -> None:
    res = _upload(db_client, "../../../outside.txt", b"escape attempt", "text/plain")
    assert res.status_code == 202
    assert res.json()["document"]["original_name"] == "outside.txt"
    files = _stored_files(storage_root)
    assert len(files) == 1
    assert files[0].resolve().is_relative_to(storage_root.resolve())
    assert not (storage_root.parent / "outside.txt").exists()


@pytest.mark.parametrize(
    ("name", "data", "mime", "status", "code"),
    [
        ("tool.exe", b"MZ\x90\x00", "application/octet-stream", 415, "unsupported_file_type"),
        ("fake.pdf", b"not really a pdf", PDF_MIME, 415, "signature_mismatch"),
        ("fake.docx", pdf_bytes(), DOCX_MIME, 415, "signature_mismatch"),
        ("image.txt", b"text", "image/png", 415, "mime_mismatch"),
        ("latin1.txt", "café".encode("latin-1"), "text/plain", 415, "invalid_text_encoding"),
        ("empty.txt", b"", "text/plain", 422, "empty_file"),
    ],
)
def test_invalid_uploads_are_rejected_and_leave_nothing_behind(
    db_client: TestClient,
    storage_root: Path,
    name: str,
    data: bytes,
    mime: str,
    status: int,
    code: str,
) -> None:
    res = _upload(db_client, name, data, mime)
    assert res.status_code == status, res.text
    err = res.json()["error"]
    assert err["code"] == code
    assert err["request_id"] == res.headers["X-Request-ID"]
    assert _stored_files(storage_root) == []
    assert db_client.get("/api/v1/documents").json()["total"] == 0


def test_missing_file_field_is_a_validation_error(db_client: TestClient) -> None:
    res = db_client.post("/api/v1/documents", data={"other": "x"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


@pytest.fixture
def small_limit_client(db_client: TestClient) -> Iterator[TestClient]:
    """Same overrides as db_client, but a 2 KiB upload limit (middleware + storage)."""
    settings = Settings(upload_max_bytes=2048)
    app = create_app(settings)
    app.dependency_overrides.update(db_client.app.dependency_overrides)  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_oversized_request_is_rejected_before_reading(
    small_limit_client: TestClient, storage_root: Path
) -> None:
    big = b"x" * (2 * 1024 * 1024)  # above limit + multipart allowance
    res = _upload(small_limit_client, "big.txt", big, "text/plain")
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"
    assert _stored_files(storage_root) == []


def test_file_over_limit_within_multipart_allowance_is_rejected_while_streaming(
    small_limit_client: TestClient, storage_root: Path
) -> None:
    res = _upload(small_limit_client, "big.txt", b"x" * 4096, "text/plain")
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"
    assert [p for p in _stored_files(storage_root)] == []


def test_upload_without_content_length_is_refused(db_client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"--b\r\nContent-Disposition: form-data; name=file; filename=a.txt\r\n\r\n"
        yield b"hi\r\n--b--\r\n"

    res = db_client.post(
        "/api/v1/documents",
        content=chunks(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )
    assert res.status_code == 411
    assert res.json()["error"]["code"] == "length_required"


def test_upload_policy_reports_formats_and_limit(db_client: TestClient) -> None:
    res = db_client.get("/api/v1/documents/upload-policy")
    assert res.status_code == 200
    body = res.json()
    assert body["max_bytes"] == get_settings().upload_max_bytes
    assert [f["file_type"] for f in body["formats"]] == ["pdf", "docx", "txt", "md"]
    assert body["formats"][3]["extensions"] == [".md", ".markdown"]


def test_list_is_paginated_newest_first(db_client: TestClient) -> None:
    for i in range(3):
        assert _upload(db_client, f"n{i}.txt", f"doc {i}".encode(), "text/plain").status_code == 202
    first = db_client.get("/api/v1/documents", params={"limit": 2}).json()
    assert first["total"] == 3
    assert first["limit"] == 2
    assert [d["original_name"] for d in first["items"]] == ["n2.txt", "n1.txt"]
    rest = db_client.get("/api/v1/documents", params={"limit": 2, "offset": 2}).json()
    assert [d["original_name"] for d in rest["items"]] == ["n0.txt"]
    assert db_client.get("/api/v1/documents", params={"limit": 0}).status_code == 422
    assert db_client.get("/api/v1/documents", params={"limit": 101}).status_code == 422


def test_unknown_document_and_job_are_404(db_client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    res = db_client.get(f"/api/v1/documents/{missing}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "document_not_found"
    assert db_client.get(f"/api/v1/jobs/{missing}").json()["error"]["code"] == "job_not_found"
    assert db_client.get("/api/v1/documents/not-a-uuid").status_code == 422
