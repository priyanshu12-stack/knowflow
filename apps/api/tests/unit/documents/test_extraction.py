"""ING-06..08: extraction keeps pages and heading paths, normalizes safely and enforces limits."""

from pathlib import Path

import pytest

from app.modules.documents.extraction import (
    ExtractionError,
    Limits,
    extract,
    extract_with_timeout,
    normalize,
)
from tests.files import pdf_bytes, real_docx_bytes, text_pdf_bytes

LIMITS = Limits(max_pages=50, max_chars=100_000)


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_pdf_pages_keep_their_numbers(tmp_path: Path) -> None:
    path = write(tmp_path, "a.pdf", text_pdf_bytes(["Alpha policy text", "Beta clause 7.2"]))
    result = extract(path, "pdf", LIMITS)
    assert result.page_count == 2
    assert result.granularity == "page"
    assert [u.page for u in result.units] == [1, 2]
    assert "Beta clause 7.2" in result.units[1].text


def test_pdf_without_text_layer_is_rejected_plainly(tmp_path: Path) -> None:
    path = write(tmp_path, "scan.pdf", text_pdf_bytes(["", ""]))
    with pytest.raises(ExtractionError) as err:
        extract(path, "pdf", LIMITS)
    assert err.value.code == "no_text_layer"
    assert "OCR" in err.value.message


def test_pdf_page_limit(tmp_path: Path) -> None:
    path = write(tmp_path, "long.pdf", text_pdf_bytes(["p"] * 3))
    with pytest.raises(ExtractionError) as err:
        extract(path, "pdf", Limits(max_pages=2, max_chars=1000))
    assert err.value.code == "too_many_pages"


def test_corrupt_pdf_is_not_retryable(tmp_path: Path) -> None:
    path = write(tmp_path, "bad.pdf", pdf_bytes())
    with pytest.raises(ExtractionError) as err:
        extract(path, "pdf", LIMITS)
    assert err.value.code in {"pdf_unreadable", "no_text_layer"}
    assert not err.value.retryable


def test_docx_heading_paths_and_tables(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "h.docx", real_docx_bytes()), "docx", LIMITS)
    assert result.granularity == "section"
    leave = next(u for u in result.units if u.section_path == ("Employee Handbook", "Leave"))
    assert "24 days" in leave.text
    assert "Sick | 10" in leave.text
    travel = next(u for u in result.units if u.section_path[-1] == "Travel")
    assert travel.section_path == ("Employee Handbook", "Travel")  # sibling replaces, not nests


def test_markdown_sections_ignore_headings_in_code(tmp_path: Path) -> None:
    md = (
        "# Guide\nIntro.\n\n## Setup\n```bash\n# not a heading\nmake setup\n```\n\n"
        "## Usage\nRun it.\n"
    )
    result = extract(write(tmp_path, "g.md", md.encode()), "md", LIMITS)
    assert [u.section_path for u in result.units] == [
        ("Guide",),
        ("Guide", "Setup"),
        ("Guide", "Usage"),
    ]
    assert "# not a heading" in result.units[1].text


def test_text_file_is_document_granularity_and_rejects_bad_utf8(tmp_path: Path) -> None:
    result = extract(write(tmp_path, "a.txt", b"\xef\xbb\xbfHello\r\nworld"), "txt", LIMITS)
    assert result.granularity == "document"
    assert result.units[0].text == "Hello\nworld"
    with pytest.raises(ExtractionError) as err:
        extract(write(tmp_path, "b.txt", b"\xff\xfe\x00bad"), "txt", LIMITS)
    assert err.value.code == "text_not_utf8"


def test_empty_and_oversized_text(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match="no text"):
        extract(write(tmp_path, "e.md", b"   \n\n "), "md", LIMITS)
    with pytest.raises(ExtractionError) as err:
        extract(write(tmp_path, "big.txt", b"x" * 2000), "txt", Limits(max_pages=1, max_chars=1000))
    assert err.value.code == "too_much_text"


def test_normalize_keeps_structure_but_removes_noise() -> None:
    raw = "Table:\n| a | b |\n\n\n\n\x00code\x07  \r\nid_42" + chr(0xA0) + "x"
    assert normalize(raw) == "Table:\n| a | b |\n\ncode\nid_42 x"


def test_subprocess_extraction_returns_result_and_safe_errors(tmp_path: Path) -> None:
    ok = extract_with_timeout(write(tmp_path, "a.md", b"# T\nbody"), "md", LIMITS, 60)
    assert ok.units[0].section_path == ("T",)
    with pytest.raises(ExtractionError) as err:
        extract_with_timeout(write(tmp_path, "e.txt", b" "), "txt", LIMITS, 60)
    assert err.value.code == "empty_document"
