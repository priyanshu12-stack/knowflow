"""Text-to-SQL with clarification (TRD §6.3, §10; PRD §5.5, Journey C).

Flow for one question:
1. Deterministic glossary check: if the question uses a term the glossary marks *ambiguous*
   (e.g. "best customers") and the user hasn't chosen what it means, return a clarification with
   the glossary's 2-4 options. No model call, no SQL, nothing executed.
2. One structured model call (prompt `sql-v1`): given the allow-listed schema, glossary
   definitions (including the user's choice) and today's date, the model returns either SQL or
   its own clarification request (for ambiguity the glossary doesn't cover) or "unsupported".
3. SQLGlot validation (validation.py). Rejected SQL is never executed.
4. Read-only execution with timeouts and a row cap (database.py).

The database's rows are facts; the model's `explanation` and `assumptions` are its
interpretation, and the UI labels them that way.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.modules.models.interfaces import ChatMessage, ChatModel, ModelError
from app.modules.models.ollama import parse_json_object

PROMPT_VERSION = "sql-v3"  # v3: FK join hints, worked example, larger output budget


@dataclass
class GlossaryEntry:
    term: str
    kind: Literal["definition", "ambiguous"]
    definition: str | None = None
    synonyms: list[str] = field(default_factory=list)
    options: list[dict[str, str]] = field(default_factory=list)  # {id, label, definition}


@dataclass
class Choice:
    term: str
    option_id: str | None = None
    custom_definition: str | None = None


def _pattern(phrase: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in phrase.lower().split()]
    # Allow simple plurals on the last word: "customer" matches "customers".
    return re.compile(r"\b" + r"\s+".join(words) + r"(?:s|es)?\b")


def matching_terms(question: str, glossary: list[GlossaryEntry]) -> list[GlossaryEntry]:
    q = question.lower()
    return [g for g in glossary if any(_pattern(p).search(q) for p in [g.term, *g.synonyms])]


def pending_clarification(
    question: str, glossary: list[GlossaryEntry], choices: list[Choice]
) -> GlossaryEntry | None:
    chosen = {c.term.lower() for c in choices}
    for entry in matching_terms(question, glossary):
        if entry.kind == "ambiguous" and entry.term.lower() not in chosen:
            return entry
    return None


def resolved_definitions(
    question: str, glossary: list[GlossaryEntry], choices: list[Choice]
) -> list[tuple[str, str]]:
    """(term, definition) pairs the model must follow for this question."""
    out: list[tuple[str, str]] = []
    by_term = {g.term.lower(): g for g in glossary}
    for c in choices:
        entry = by_term.get(c.term.lower())
        if c.custom_definition:
            out.append((c.term, c.custom_definition.strip()))
        elif entry is not None:
            opt = next((o for o in entry.options if o.get("id") == c.option_id), None)
            if opt:
                out.append((entry.term, opt["definition"]))
    for entry in matching_terms(question, glossary):
        if entry.kind == "definition" and entry.definition:
            out.append((entry.term, entry.definition))
    return out


class ClarificationOption(BaseModel):
    label: str = Field(max_length=120)
    definition: str = Field(max_length=500)


class ModelClarification(BaseModel):
    question: str = Field(max_length=300)
    missing_concept: str = Field(max_length=120)
    options: list[ClarificationOption] = Field(min_length=2, max_length=4)


class ModelSqlOutput(BaseModel):
    status: Literal["ready", "clarification_required", "unsupported"]
    sql: str | None = Field(default=None, max_length=10_000)
    explanation: str = Field(default="", max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    tables: list[str] = Field(default_factory=list, max_length=20)
    clarification: ModelClarification | None = None
    reason: str | None = Field(default=None, max_length=500)


SQL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ready", "clarification_required", "unsupported"]},
        "sql": {"type": ["string", "null"]},
        "explanation": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "tables": {"type": "array", "items": {"type": "string"}},
        "clarification": {
            "type": ["object", "null"],
            "properties": {
                "question": {"type": "string"},
                "missing_concept": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "definition": {"type": "string"},
                        },
                        "required": ["label", "definition"],
                    },
                },
            },
        },
        "reason": {"type": ["string", "null"]},
    },
    "required": ["status", "explanation"],
}

SYSTEM_PROMPT = """You translate business questions into ONE read-only PostgreSQL SELECT query \
for the schema below. You never write data and never use any table outside the schema.

Rules:
1. Output JSON only, matching the schema you were given.
2. If the question is clear, set status "ready" and put a single SELECT (CTEs allowed) in "sql". \
Always schema-qualify tables (e.g. sales.orders). Prefer explicit JOINs and readable aliases. \
Add ORDER BY for rankings and a LIMIT for "top" questions.
3. Follow every business definition listed under "Definitions" exactly.
4. Resolve relative dates against today's date given below (for example "last month" is the \
previous calendar month; use date ranges, not EXTRACT on the current month).
5. If the question depends on a business term with several plausible meanings that no \
definition settles, set status "clarification_required" and give 2-4 concrete options. Do not \
guess.
6. If the question can't be answered from this schema, or asks to change data, set status \
"unsupported" with a short "reason".
7. Keep the query as simple as possible: avoid CTEs and window functions unless needed, and \
reference only columns and tables that exist, spelled exactly as in the schema.
8. "explanation" says in plain English what the query computes. "assumptions" lists anything \
you assumed (date range, how refunds are treated).

Example of the expected style (for a different schema and question):
SELECT o.customer_id, COUNT(*) AS paid_orders
FROM shop.orders o
WHERE o.status = 'paid' AND o.order_date >= DATE '2026-01-01' AND o.order_date < DATE '2026-02-01'
GROUP BY o.customer_id
ORDER BY paid_orders DESC
LIMIT 10"""


@dataclass
class Repair:
    """A previous attempt the database rejected; the model gets one chance to fix it."""

    sql: str
    error: str


def build_prompt(
    question: str,
    schema_text: str,
    definitions: list[tuple[str, str]],
    today: date,
    repair: Repair | None = None,
) -> str:
    defs = "\n".join(f"- {t}: {d}" for t, d in definitions) or "- (none)"
    prompt = (
        f"Today's date: {today.isoformat()}\n\nSchema:\n{schema_text}\n\n"
        f"Definitions:\n{defs}\n\nQuestion: {question}"
    )
    if repair is not None:
        prompt += (
            f"\n\nYour previous query failed.\nPrevious SQL:\n{repair.sql}\n"
            f"Database error: {repair.error}\nReturn a corrected query."
        )
    return prompt


def generate(
    chat: ChatModel,
    question: str,
    schema_text: str,
    definitions: list[tuple[str, str]],
    today: date,
    repair: Repair | None = None,
) -> tuple[ModelSqlOutput, int]:
    result = chat.complete(
        [
            ChatMessage("system", SYSTEM_PROMPT),
            ChatMessage("user", build_prompt(question, schema_text, definitions, today, repair)),
        ],
        temperature=0.0,
        json_schema=SQL_SCHEMA,
        num_predict=1000,
    )
    try:
        parsed = ModelSqlOutput.model_validate(parse_json_object(result.content))
    except (ValidationError, ModelError) as exc:
        raise ModelError(
            "model_invalid_output",
            "The model's SQL answer didn't match the expected format. Try rephrasing.",
            retryable=True,
        ) from exc
    if parsed.status == "ready" and not (parsed.sql and parsed.sql.strip()):
        raise ModelError("model_invalid_output", "The model returned no SQL.", retryable=True)
    if parsed.status == "clarification_required" and parsed.clarification is None:
        raise ModelError(
            "model_invalid_output",
            "The model asked for clarification without options.",
            retryable=True,
        )
    return parsed, result.latency_ms
