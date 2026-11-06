"""Local file storage for uploads (ING-03, ING-04, SEC-06).

- Files live under a non-public root and are named by generated keys
  (`<workspace_id>/<document_id>`), never by the user's filename.
- Every key is validated and its resolved path must stay inside the root (path traversal).
- Uploads stream into `<root>/.incoming/` while being hashed and size-checked, then move into
  place with an atomic rename once the database row is ready.
"""

import contextlib
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.errors import AppError

logger = logging.getLogger(__name__)

_CHUNK = 1024 * 1024
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_KEY_RE = re.compile(rf"^{_UUID}/{_UUID}$")
_INCOMING = ".incoming"


class StorageError(AppError):
    def __init__(self, message: str = "The file could not be stored.") -> None:
        super().__init__("storage_error", message, 500)


@dataclass(frozen=True)
class IncomingFile:
    path: Path
    size_bytes: int
    sha256: str


def make_storage_key(workspace_id: uuid.UUID, document_id: uuid.UUID) -> str:
    return f"{workspace_id}/{document_id}"


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _incoming_dir(self) -> Path:
        path = self.root / _INCOMING
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, key: str) -> Path:
        """Resolve a storage key to a path, refusing anything that could escape the root."""
        if not _KEY_RE.fullmatch(key):
            raise ValueError("invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("storage key escapes the storage root")
        return path

    def receive(self, source: BinaryIO, max_bytes: int) -> IncomingFile:
        """Stream `source` to an incoming file, hashing it and enforcing `max_bytes`."""
        path = self._incoming_dir() / f"{uuid.uuid4()}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("xb") as out:
                while chunk := source.read(_CHUNK):
                    size += len(chunk)
                    if size > max_bytes:
                        raise AppError(
                            "file_too_large",
                            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
                            413,
                        )
                    digest.update(chunk)
                    out.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        if size == 0:
            path.unlink(missing_ok=True)
            raise AppError("empty_file", "The file is empty.", 422)
        return IncomingFile(path=path, size_bytes=size, sha256=digest.hexdigest())

    def discard(self, incoming: IncomingFile) -> None:
        incoming.path.unlink(missing_ok=True)

    def commit(self, incoming: IncomingFile, key: str) -> Path:
        """Move an incoming file to its final location. Never overwrites an existing file."""
        target = self.path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise StorageError()
        try:
            os.replace(incoming.path, target)
        except OSError as exc:
            logger.error("storage_commit_failed", extra={"error_type": type(exc).__name__})
            raise StorageError() from exc
        return target

    def delete(self, key: str) -> bool:
        """Remove a stored file. Missing files are fine: deletion is idempotent."""
        path = self.path_for(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        with contextlib.suppress(OSError):
            path.parent.rmdir()  # drop the workspace folder once it's empty
        return True
