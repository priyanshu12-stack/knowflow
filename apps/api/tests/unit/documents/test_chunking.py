"""ADR-005: fixed vs recursive chunking produce comparable, traceable chunks."""

import pytest

from app.modules.documents.chunking import ChunkingConfig, chunk_fixed, chunk_recursive
from app.modules.documents.extraction import Unit

CFG = ChunkingConfig(size=200, overlap=40)


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_fixed_windows_overlap_and_track_pages() -> None:
    units = [Unit(text=words(60, "a"), page=1), Unit(text=words(60, "b"), page=2)]
    chunks = chunk_fixed(units, CFG)
    assert len(chunks) > 2
    assert all(len(c.text) <= CFG.size for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2
    assert any(c.page_start == 1 and c.page_end == 2 for c in chunks)  # crosses the boundary
    # overlap: the start of chunk n+1 repeats the tail of chunk n
    assert chunks[1].text.split()[0] in chunks[0].text


def test_fixed_does_not_split_words() -> None:
    chunks = chunk_fixed([Unit(text=words(200))], CFG)
    vocabulary = set(words(200).split())
    assert all(set(c.text.split()) <= vocabulary for c in chunks)


def test_recursive_respects_unit_boundaries_and_sections() -> None:
    units = [
        Unit(text="Intro paragraph.", section_path=("Guide",)),
        Unit(text=("Sentence one. " * 30).strip(), section_path=("Guide", "Setup")),
    ]
    chunks = chunk_recursive(units, CFG)
    assert chunks[0].text == "Intro paragraph."
    assert chunks[0].section_path == "Guide"
    assert all(c.section_path == "Guide > Setup" for c in chunks[1:])
    assert all(len(c.text) <= CFG.size for c in chunks)
    assert all(c.text.endswith(".") for c in chunks[1:])  # ends on sentence boundaries


def test_recursive_hard_splits_unbreakable_text() -> None:
    chunks = chunk_recursive([Unit(text="x" * 450, page=3)], CFG)
    assert [len(c.text) for c in chunks] == [200, 200, 50]
    assert {c.page_start for c in chunks} == {3}


def test_chunk_metadata() -> None:
    (c,) = chunk_recursive([Unit(text="abcd" * 10)], CFG)
    assert c.char_count == 40
    assert c.token_count == 10
    assert len(c.content_hash) == 64


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="overlap"):
        ChunkingConfig(size=200, overlap=150)
