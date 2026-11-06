"""Chunking strategies (TRD §9 S1/S2, ADR-005).

- `fixed`: the naive baseline. Concatenates the whole document and cuts fixed-size character
  windows with overlap, ignoring structure. Page ranges are tracked through offsets.
- `recursive`: structure-aware. Never crosses a unit (page / heading section) boundary; splits a
  unit on paragraph, line, sentence and word separators in that order and greedily merges the
  pieces up to the size budget, so chunks end on natural boundaries.

Both produce the same `Chunk` shape so retrieval and evaluation can compare them fairly.
Sizes are in characters; `token_count` is an estimate (≈4 chars/token for English) because the
exact tokenizer belongs to the embedding model and is not available offline.
"""

import hashlib
import math
from dataclasses import dataclass
from typing import Literal

from app.modules.documents.extraction import Unit

Strategy = Literal["fixed", "recursive"]
STRATEGIES: tuple[Strategy, ...] = ("fixed", "recursive")
SECTION_SEPARATOR = " > "


@dataclass(frozen=True)
class ChunkingConfig:
    size: int = 1200
    overlap: int = 200

    def __post_init__(self) -> None:
        if self.size < 100 or not 0 <= self.overlap < self.size // 2:
            raise ValueError("chunk size must be >= 100 and overlap < size / 2")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    strategy: Strategy

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def token_count(self) -> int:
        return max(1, math.ceil(len(self.text) / 4))

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _section(unit: Unit) -> str | None:
    return SECTION_SEPARATOR.join(unit.section_path) or None


def _snap_end(text: str, start: int, end: int) -> int:
    """Move a window end back to the last whitespace so words aren't cut, if one is close."""
    if end >= len(text):
        return len(text)
    space = text.rfind(" ", start + (end - start) // 2, end)
    newline = text.rfind("\n", start + (end - start) // 2, end)
    cut = max(space, newline)
    return cut if cut > start else end


def chunk_fixed(units: list[Unit], cfg: ChunkingConfig) -> list[Chunk]:
    joined: list[str] = []
    spans: list[tuple[int, int, Unit]] = []  # (start, end, unit) offsets into the joined text
    pos = 0
    for unit in units:
        joined.append(unit.text)
        spans.append((pos, pos + len(unit.text), unit))
        pos += len(unit.text) + 2
    text = "\n\n".join(joined)

    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = _snap_end(text, start, start + cfg.size)
        piece = text[start:end].strip()
        if piece:
            covered = [u for s, e, u in spans if s < end and e > start]
            pages = [u.page for u in covered if u.page is not None]
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=piece,
                    page_start=min(pages) if pages else None,
                    page_end=max(pages) if pages else None,
                    section_path=_section(covered[0]) if covered else None,
                    strategy="fixed",
                )
            )
        if end >= len(text):
            break
        start = max(end - cfg.overlap, start + 1)
    return chunks


_SEPARATORS = ("\n\n", "\n", ". ", " ")


def _split(text: str, size: int, separators: tuple[str, ...] = _SEPARATORS) -> list[str]:
    """Split text into pieces no longer than `size`, preferring the coarsest separator."""
    if len(text) <= size:
        return [text]
    if not separators:
        return [text[i : i + size] for i in range(0, len(text), size)]
    sep, rest = separators[0], separators[1:]
    parts = text.split(sep)
    if len(parts) == 1:
        return _split(text, size, rest)
    pieces: list[str] = []
    for i, part in enumerate(parts):
        # Keep the separator with the preceding part so sentences keep their punctuation.
        chunk = part + (sep if i < len(parts) - 1 else "")
        pieces.extend(_split(chunk, size, rest) if len(chunk) > size else [chunk])
    return pieces


def _merge(pieces: list[str], size: int) -> list[str]:
    merged: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > size:
            merged.append(current)
            current = ""
        current += piece
    if current:
        merged.append(current)
    return [m.strip() for m in merged if m.strip()]


def chunk_recursive(units: list[Unit], cfg: ChunkingConfig) -> list[Chunk]:
    chunks: list[Chunk] = []
    for unit in units:
        for piece in _merge(_split(unit.text, cfg.size), cfg.size):
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=piece,
                    page_start=unit.page,
                    page_end=unit.page,
                    section_path=_section(unit),
                    strategy="recursive",
                )
            )
    return chunks


def chunk(units: list[Unit], strategy: Strategy, cfg: ChunkingConfig) -> list[Chunk]:
    if strategy == "fixed":
        return chunk_fixed(units, cfg)
    return chunk_recursive(units, cfg)
