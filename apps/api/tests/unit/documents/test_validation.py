"""ING-01 / ING-02 / SEC-01: allowlist, declared MIME and file-signature checks."""

from pathlib import Path

import pytest

from app.modules.documents.validation import (
    UploadRejectedError,
    check_declared_mime,
    check_signature,
    format_for_filename,
    sanitize_filename,
)
from tests.files import DOCX_MIME, docx_bytes, pdf_bytes, zip_without_word_body


@pytest.mark.parametrize(
    ("name", "file_type"),
    [
        ("report.pdf", "pdf"),
        ("Report.PDF", "pdf"),
        ("notes.docx", "docx"),
        ("a.txt", "txt"),
        ("README.md", "md"),
        ("guide.markdown", "md"),
    ],
)
def test_supported_extensions(name: str, file_type: str) -> None:
    assert format_for_filename(name).file_type == file_type


@pytest.mark.parametrize(
    "name", ["setup.exe", "data.csv", "old.doc", "scan.png", "noext", "x.pdf.exe"]
)
def test_unsupported_extensions_are_rejected(name: str) -> None:
    with pytest.raises(UploadRejectedError) as err:
        format_for_filename(name)
    assert err.value.code == "unsupported_file_type"
    assert err.value.status_code == 415


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.txt", "passwd.txt"),
        ("C:\\Users\\me\\secret.pdf", "secret.pdf"),
        ("bad\x00name\x1f.md", "badname.md"),
        ("  spaced.txt  ", "spaced.txt"),
    ],
)
def test_sanitize_filename_keeps_only_a_display_name(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "../", "\x00\x01", "..."])
def test_sanitize_filename_rejects_unusable_names(raw: str | None) -> None:
    with pytest.raises(UploadRejectedError) as err:
        sanitize_filename(raw)
    assert err.value.code == "invalid_filename"


def test_sanitize_filename_truncates_but_keeps_extension() -> None:
    name = sanitize_filename("a" * 400 + ".docx")
    assert len(name) == 255
    assert name.endswith(".docx")


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("a.pdf", "application/pdf"),
        ("a.pdf", "Application/PDF; charset=binary"),
        ("a.docx", DOCX_MIME),
        ("a.md", "text/markdown"),
        ("a.md", "text/plain"),
        ("a.md", "application/octet-stream"),
        ("a.txt", ""),
        ("a.txt", None),
    ],
)
def test_declared_mime_accepted(name: str, mime: str | None) -> None:
    check_declared_mime(format_for_filename(name), mime)


@pytest.mark.parametrize(
    ("name", "mime"),
    [("a.pdf", "text/plain"), ("a.txt", "image/png"), ("a.docx", "application/pdf")],
)
def test_declared_mime_mismatch_rejected(name: str, mime: str) -> None:
    with pytest.raises(UploadRejectedError) as err:
        check_declared_mime(format_for_filename(name), mime)
    assert err.value.code == "mime_mismatch"


def _write(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "upload.bin"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("a.pdf", pdf_bytes()),
        ("a.pdf", b"\n\n" + pdf_bytes()),  # small leading junk is allowed by the PDF spec
        ("a.docx", docx_bytes()),
        ("a.txt", "Plain text with \u00fcn\u00efcode.\n".encode()),
        ("a.md", b"\xef\xbb\xbf# Heading with BOM\n"),
    ],
)
def test_valid_signatures(tmp_path: Path, name: str, data: bytes) -> None:
    check_signature(format_for_filename(name), _write(tmp_path, data))


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("a.pdf", b"MZ\x90\x00 this is an exe", "signature_mismatch"),
        ("a.pdf", b"x" * 2048 + b"%PDF-1.4", "signature_mismatch"),
        ("a.docx", pdf_bytes(), "signature_mismatch"),
        ("a.docx", zip_without_word_body(), "signature_mismatch"),
        ("a.docx", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1 encrypted OLE", "signature_mismatch"),
        ("a.txt", b"text\x00with nul", "signature_mismatch"),
        ("a.txt", "caf\u00e9".encode("latin-1"), "invalid_text_encoding"),
        ("a.md", "# UTF-16".encode("utf-16"), "signature_mismatch"),
    ],
)
def test_invalid_signatures(tmp_path: Path, name: str, data: bytes, code: str) -> None:
    with pytest.raises(UploadRejectedError) as err:
        check_signature(format_for_filename(name), _write(tmp_path, data))
    assert err.value.code == code
    assert err.value.status_code == 415
