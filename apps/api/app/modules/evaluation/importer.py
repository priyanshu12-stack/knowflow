"""CSV / JSONL import of evaluation cases with row-level errors (TRD §8, PRD §5.4).

JSONL: one object per line with `question` (required), `id`, `split` (dev|test),
`reference_answer`, `answerable`, `expected_evidence` [{document, quote?, page?}],
`expected_chunk_ids`, `tags`.
CSV: the same columns. `expected_evidence` may be a JSON string, or use the simple columns
`evidence_document`, `evidence_quote`, `evidence_page` for one evidence item. List columns
(`tags`, `expected_chunk_ids`) are separated by `;`.
"""

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024


class EvidenceIn(BaseModel):
    document: str = Field(min_length=1, max_length=255)
    quote: str | None = Field(default=None, max_length=2000)
    page: int | None = Field(default=None, ge=1)


class CaseIn(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    split: str = "dev"
    question: str = Field(min_length=1, max_length=2000)
    reference_answer: str | None = Field(default=None, max_length=5000)
    answerable: bool = True
    expected_evidence: list[EvidenceIn] = Field(default_factory=list, max_length=20)
    expected_chunk_ids: list[str] = Field(default_factory=list, max_length=50)
    expected_sql: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("split")
    @classmethod
    def split_valid(cls, v: str) -> str:
        v = v.strip().lower() or "dev"
        if v not in ("dev", "test"):
            raise ValueError("split must be 'dev' or 'test'")
        return v

    @field_validator("question")
    @classmethod
    def strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


@dataclass
class RowError:
    row: int
    message: str


def _list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(";") if v.strip()]


def _bool(value: Any) -> Any:
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("", "true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    return value


def _from_csv_row(row: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {
        k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k
    }
    evidence = data.pop("expected_evidence", "") or ""
    doc = data.pop("evidence_document", "")
    quote = data.pop("evidence_quote", "")
    page = data.pop("evidence_page", "")
    if evidence:
        data["expected_evidence"] = json.loads(evidence)
    elif doc:
        data["expected_evidence"] = [
            {"document": doc, "quote": quote or None, "page": int(page) if page else None}
        ]
    data["tags"] = _list(data.get("tags"))
    data["expected_chunk_ids"] = _list(data.get("expected_chunk_ids"))
    data["answerable"] = _bool(data.get("answerable", True))
    return {k: v for k, v in data.items() if v != "" or k == "question"}


def parse_cases(filename: str, content: bytes) -> tuple[list[CaseIn], list[RowError]]:
    if len(content) > MAX_BYTES:
        return [], [RowError(0, f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB.")]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [RowError(0, "The file isn't valid UTF-8.")]
    rows: list[tuple[int, Any]] = []
    errors: list[RowError] = []
    lower = filename.lower()
    if lower.endswith((".jsonl", ".ndjson")):
        for n, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                try:
                    rows.append((n, json.loads(line)))
                except json.JSONDecodeError as exc:
                    errors.append(RowError(n, f"Invalid JSON: {exc.msg}."))
    elif lower.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "question" not in [f.strip() for f in reader.fieldnames]:
            return [], [RowError(1, "The CSV needs a 'question' column.")]
        for n, row in enumerate(reader, start=2):
            try:
                rows.append((n, _from_csv_row(row)))
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(RowError(n, f"Invalid evidence columns: {exc}."))
    else:
        return [], [RowError(0, "Upload a .jsonl or .csv file.")]

    if len(rows) > MAX_ROWS:
        return [], [RowError(0, f"Too many rows ({len(rows)}); the limit is {MAX_ROWS}.")]
    cases: list[CaseIn] = []
    seen: set[str] = set()
    for n, raw in rows:
        if not isinstance(raw, dict):
            errors.append(RowError(n, "Each row must be an object."))
            continue
        try:
            case = CaseIn.model_validate(raw)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(p) for p in first["loc"]) or "row"
            errors.append(RowError(n, f"{field}: {first['msg']}"))
            continue
        case.id = case.id or f"row-{n}"
        if case.id in seen:
            errors.append(RowError(n, f"Duplicate id '{case.id}'."))
            continue
        if case.answerable and not case.expected_evidence and not case.expected_chunk_ids:
            errors.append(
                RowError(n, "Answerable cases need expected_evidence or expected_chunk_ids.")
            )
            continue
        seen.add(case.id)
        cases.append(case)
    return cases, errors
