"""ING-03 / ING-04 / SEC-06: generated keys, SHA-256, size limit and path-traversal protection."""

import hashlib
import io
import uuid
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.modules.documents.storage import FileStorage, StorageError, make_storage_key


@pytest.fixture
def storage(tmp_path: Path) -> FileStorage:
    return FileStorage(tmp_path / "storage")


def _key() -> str:
    return make_storage_key(uuid.uuid4(), uuid.uuid4())


def test_receive_hashes_and_counts(storage: FileStorage) -> None:
    data = b"hello knowflow" * 1000
    incoming = storage.receive(io.BytesIO(data), max_bytes=1_000_000)
    assert incoming.size_bytes == len(data)
    assert incoming.sha256 == hashlib.sha256(data).hexdigest()
    assert incoming.path.read_bytes() == data
    assert incoming.path.is_relative_to(storage.root)


def test_receive_enforces_size_limit_and_cleans_up(storage: FileStorage) -> None:
    with pytest.raises(AppError) as err:
        storage.receive(io.BytesIO(b"x" * 2048), max_bytes=1024)
    assert err.value.code == "file_too_large"
    assert err.value.status_code == 413
    assert list((storage.root / ".incoming").iterdir()) == []


def test_receive_rejects_empty_files(storage: FileStorage) -> None:
    with pytest.raises(AppError) as err:
        storage.receive(io.BytesIO(b""), max_bytes=1024)
    assert err.value.code == "empty_file"
    assert list((storage.root / ".incoming").iterdir()) == []


def test_commit_moves_to_generated_key_and_delete_is_idempotent(storage: FileStorage) -> None:
    incoming = storage.receive(io.BytesIO(b"content"), max_bytes=1024)
    key = _key()
    path = storage.commit(incoming, key)
    assert path == storage.path_for(key)
    assert path.read_bytes() == b"content"
    assert not incoming.path.exists()
    assert storage.delete(key) is True
    assert not path.exists()
    assert storage.delete(key) is False


def test_commit_never_overwrites(storage: FileStorage) -> None:
    key = _key()
    storage.commit(storage.receive(io.BytesIO(b"first"), max_bytes=1024), key)
    with pytest.raises(StorageError):
        storage.commit(storage.receive(io.BytesIO(b"second"), max_bytes=1024), key)
    assert storage.path_for(key).read_bytes() == b"first"


@pytest.mark.parametrize(
    "key",
    [
        "../outside",
        "../../etc/passwd",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        f"{uuid.uuid4()}/../../{uuid.uuid4()}",
        f"{uuid.uuid4()}/{uuid.uuid4()}/extra",
        f"{uuid.uuid4()}\\{uuid.uuid4()}",
        "report.pdf",
        "",
    ],
)
def test_path_for_rejects_anything_but_generated_keys(storage: FileStorage, key: str) -> None:
    with pytest.raises(ValueError, match="storage key"):
        storage.path_for(key)


def test_resolved_path_stays_inside_root(storage: FileStorage) -> None:
    path = storage.path_for(_key())
    assert path.is_relative_to(storage.root)
