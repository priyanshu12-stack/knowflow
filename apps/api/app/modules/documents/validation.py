"""Upload validation (ING-01, ING-02, SEC-01): extension allowlist, declared MIME, file signature.

Nothing here trusts the client. The extension picks the expected format, the browser-declared MIME
must agree with it, and the stored bytes must actually be that format. The canonical MIME stored on
the document comes from this table, never from the request.
"""

import codecs
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.errors import AppError

FileType = Literal["pdf", "docx", "txt", "md"]

_READ_CHUNK = 64 * 1024
_MAX_NAME_LENGTH = 255
_MAX_DOCX_ENTRIES = 10_000
# Browsers and OSes send these when they don't know a type (common for .md on Windows).
_GENERIC_MIMES = frozenset({"", "application/octet-stream"})


@dataclass(frozen=True)
class FileFormat:
    file_type: FileType
    label: str
    mime_type: str
    extensions: tuple[str, ...]
    accepted_mimes: frozenset[str]


SUPPORTED_FORMATS: tuple[FileFormat, ...] = (
    FileFormat(
        "pdf", "PDF (text-based)", "application/pdf", (".pdf",), frozenset({"application/pdf"})
    ),
    FileFormat(
        "docx",
        "Word document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        (".docx",),
        frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ),
    FileFormat("txt", "Plain text", "text/plain", (".txt",), frozenset({"text/plain"})),
    FileFormat(
        "md",
        "Markdown",
        "text/markdown",
        (".md", ".markdown"),
        frozenset({"text/markdown", "text/x-markdown", "text/plain"}),
    ),
)
_BY_EXTENSION = {ext: fmt for fmt in SUPPORTED_FORMATS for ext in fmt.extensions}


class UploadRejectedError(AppError):
    """A user-correctable upload problem. Messages name the file problem, never internals."""


def sanitize_filename(raw: str | None) -> str:
    """Display name only: last path segment, no control characters, NFC, at most 255 chars."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip().strip(".")
    if not name:
        raise UploadRejectedError("invalid_filename", "The file has no usable name.", 422)
    if len(name) > _MAX_NAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        keep = _MAX_NAME_LENGTH - len(dot + ext)
        name = (stem[:keep] + dot + ext) if dot and keep > 0 else name[:_MAX_NAME_LENGTH]
    return name


def format_for_filename(name: str) -> FileFormat:
    fmt = _BY_EXTENSION.get(Path(name).suffix.lower())
    if fmt is None:
        allowed = ", ".join(ext for f in SUPPORTED_FORMATS for ext in f.extensions)
        raise UploadRejectedError(
            "unsupported_file_type",
            f"This file type isn't supported. Upload one of: {allowed}.",
            415,
        )
    return fmt


def check_declared_mime(fmt: FileFormat, declared: str | None) -> None:
    mime = (declared or "").split(";", 1)[0].strip().lower()
    if mime not in _GENERIC_MIMES and mime not in fmt.accepted_mimes:
        raise UploadRejectedError(
            "mime_mismatch",
            f"The file is labelled as {mime}, which doesn't match its {fmt.extensions[0]} "
            "extension.",
            415,
        )


def _signature_error(fmt: FileFormat, why: str) -> UploadRejectedError:
    return UploadRejectedError(
        "signature_mismatch", f"The file content isn't a valid {fmt.label}: {why}.", 415
    )


def _check_pdf(path: Path, fmt: FileFormat) -> None:
    with path.open("rb") as fh:
        head = fh.read(1024)
    # The PDF spec allows a little leading junk before the header; 1 KiB is the common tolerance.
    if b"%PDF-" not in head:
        raise _signature_error(fmt, "the PDF header is missing")


def _check_docx(path: Path, fmt: FileFormat) -> None:
    # Only the central directory is read; nothing is extracted, so zip bombs can't expand here.
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > _MAX_DOCX_ENTRIES:
                raise _signature_error(fmt, "it contains too many parts")
            names = {info.filename for info in infos}
    except (zipfile.BadZipFile, OSError) as exc:
        # Password-protected .docx files are OLE containers, not ZIP, and end up here too.
        raise _signature_error(fmt, "it isn't a Word (.docx) package or it is encrypted") from exc
    if not {"[Content_Types].xml", "word/document.xml"} <= names:
        raise _signature_error(fmt, "the Word document body is missing")


def _check_text(path: Path, fmt: FileFormat) -> None:
    decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(_READ_CHUNK):
                if b"\x00" in chunk:
                    raise _signature_error(fmt, "it contains binary data")
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise UploadRejectedError(
            "invalid_text_encoding",
            "The text file isn't valid UTF-8. Re-save it as UTF-8 and upload it again.",
            415,
        ) from exc


_SIGNATURE_CHECKS = {"pdf": _check_pdf, "docx": _check_docx, "txt": _check_text, "md": _check_text}


def check_signature(fmt: FileFormat, path: Path) -> None:
    _SIGNATURE_CHECKS[fmt.file_type](path, fmt)
