"""Text extraction with page / heading metadata (TRD §6.1, ING-06..ING-08).

Each format becomes an ordered list of `Unit`s: a PDF page, a DOCX section under a heading, or a
Markdown section. Units keep the original (normalized) text so citations can point at a page or
heading path, and so the extraction stays inspectable.

Parsers run in a child process (`extract_with_timeout`) so a malformed or hostile file can't hang
or crash the worker: the child is killed when the timeout expires (TRD §11, "parser timeouts").
"""

import multiprocessing as mp
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Granularity = Literal["page", "section", "document"]


@dataclass(frozen=True)
class Unit:
    text: str
    page: int | None = None
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class Extraction:
    units: list[Unit]
    page_count: int | None
    granularity: Granularity
    char_count: int = field(default=0)


@dataclass(frozen=True)
class Limits:
    max_pages: int
    max_chars: int


class ExtractionError(Exception):
    """A safe, plain-language extraction failure. `retryable` is False for bad input."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def __reduce__(self) -> tuple[object, ...]:
        # Crosses the process boundary in `extract_with_timeout`; keep all fields when pickled.
        return (_rebuild_error, (self.code, self.message, self.retryable))


def _rebuild_error(code: str, message: str, retryable: bool) -> ExtractionError:
    return ExtractionError(code, message, retryable=retryable)


# --- Normalization: tidy whitespace without destroying tables, code or identifiers. ---

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_WS = re.compile(r"[ \t]+\n")
_MANY_BLANK = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text).replace(chr(0xA0), " ")  # no-break space -> space
    text = _TRAILING_WS.sub("\n", text)
    return _MANY_BLANK.sub("\n\n", text).strip()


# --- Format parsers. Each returns raw units; `extract` normalizes and applies limits. ---


def _pdf(path: Path, limits: Limits) -> tuple[list[Unit], int]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ExtractionError("pdf_encrypted", "This PDF is password-protected.")
        pages = len(reader.pages)
    except PdfReadError as exc:
        raise ExtractionError("pdf_unreadable", "The PDF could not be read.") from exc
    if pages > limits.max_pages:
        raise ExtractionError(
            "too_many_pages", f"The PDF has {pages} pages; the limit is {limits.max_pages}."
        )
    units = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pypdf raises assorted errors on malformed content streams
            raise ExtractionError(
                "pdf_unreadable", f"Page {number} of the PDF could not be read."
            ) from exc
        units.append(Unit(text=text, page=number))
    return units, pages


_HEADING_STYLE = re.compile(r"^(?:Heading|Title)\s*(\d*)$", re.IGNORECASE)


def _docx(path: Path) -> list[Unit]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(str(path))
    except Exception as exc:  # python-docx raises KeyError/BadZipFile/ValueError on bad packages
        raise ExtractionError("docx_unreadable", "The Word document could not be read.") from exc

    units: list[Unit] = []
    headings: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            units.append(Unit(text="\n\n".join(buffer), section_path=tuple(headings)))
            buffer.clear()

    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            style = block.style.name if block.style is not None else ""
            match = _HEADING_STYLE.match(style or "")
            if match and text:
                flush()
                level = int(match.group(1) or 1)
                del headings[level - 1 :]
                headings.append(text)
            elif text:
                buffer.append(text)
        elif isinstance(block, Table):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in block.rows]
            if rows:
                buffer.append("\n".join(rows))
    flush()
    return units


_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _markdown(text: str) -> list[Unit]:
    units: list[Unit] = []
    headings: list[str] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        if "".join(buffer).strip():
            units.append(Unit(text="\n".join(buffer), section_path=tuple(headings)))
        buffer.clear()

    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _ATX.match(line)
        if match:
            flush()
            level = len(match.group(1))
            del headings[level - 1 :]
            headings.append(match.group(2))
        else:
            buffer.append(line)
    flush()
    return units


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("text_not_utf8", "The text file isn't valid UTF-8.") from exc


def extract(path: Path, file_type: str, limits: Limits) -> Extraction:
    """Parse one stored file. Raises `ExtractionError` with a user-safe message."""
    page_count: int | None = None
    granularity: Granularity
    if file_type == "pdf":
        raw, page_count = _pdf(path, limits)
        granularity = "page"
    elif file_type == "docx":
        raw = _docx(path)
        granularity = "section" if any(u.section_path for u in raw) else "document"
    elif file_type == "md":
        raw = _markdown(normalize(_read_text(path)))
        granularity = "section" if any(u.section_path for u in raw) else "document"
    elif file_type == "txt":
        raw = [Unit(text=_read_text(path))]
        granularity = "document"
    else:
        raise ExtractionError("unsupported_type", f"Unsupported file type: {file_type}.")

    units = [
        Unit(text=t, page=u.page, section_path=u.section_path)
        for u in raw
        if (t := normalize(u.text))
    ]
    chars = sum(len(u.text) for u in units)
    if chars == 0:
        if file_type == "pdf":
            raise ExtractionError(
                "no_text_layer",
                "No text could be extracted. The PDF may be scanned; OCR isn't supported.",
            )
        raise ExtractionError("empty_document", "The document contains no text.")
    if chars > limits.max_chars:
        raise ExtractionError(
            "too_much_text",
            f"The document has {chars:,} characters of text; the limit is {limits.max_chars:,}.",
        )
    return Extraction(units=units, page_count=page_count, granularity=granularity, char_count=chars)


# --- Process isolation ---


def _child(path: str, file_type: str, limits: Limits) -> Extraction | ExtractionError:
    try:
        return extract(Path(path), file_type, limits)
    except ExtractionError as exc:
        return exc
    except Exception:
        return ExtractionError("extraction_failed", "The document could not be processed.")


def extract_with_timeout(
    path: Path, file_type: str, limits: Limits, timeout_seconds: float
) -> Extraction:
    """Run `extract` in a spawned child process and kill it if it runs too long."""
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1, maxtasksperchild=1) as pool:
        pending = pool.apply_async(_child, (str(path), file_type, limits))
        try:
            result = pending.get(timeout=timeout_seconds)
        except mp.TimeoutError as exc:
            pool.terminate()
            raise ExtractionError(
                "extraction_timeout",
                f"Extraction took longer than {int(timeout_seconds)} seconds and was stopped.",
            ) from exc
    if isinstance(result, ExtractionError):
        raise result
    return result
