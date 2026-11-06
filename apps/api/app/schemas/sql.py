"""SQL Analyst API contracts (TRD §8). Passwords are accepted, never returned."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

IDENT = r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$"


class ConnectionIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.\-]+$")
    port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(pattern=IDENT)
    username: str = Field(pattern=IDENT)
    password: SecretStr = Field(min_length=1, max_length=200)
    allowed_schemas: list[str] = Field(min_length=1, max_length=10)

    @field_validator("allowed_schemas")
    @classmethod
    def schemas_valid(cls, v: list[str]) -> list[str]:
        import re

        for s in v:
            if not re.fullmatch(IDENT, s) or s.lower() in ("pg_catalog", "information_schema"):
                raise ValueError(f"invalid schema name: {s}")
        return v


class ConnectionOut(BaseModel):
    id: uuid.UUID
    display_name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    allowed_schemas: list[str]
    is_demo: bool
    created_at: datetime
    # Deliberately no password field (write-only secret).


class ColumnOut(BaseModel):
    name: str
    data_type: str
    nullable: bool
    description: str | None


class TableOut(BaseModel):
    schema_name: str
    name: str
    description: str | None
    columns: list[ColumnOut]


class GlossaryOption(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=1, max_length=500)


class GlossaryTermIO(BaseModel):
    term: str = Field(min_length=1, max_length=80)
    kind: Literal["definition", "ambiguous"]
    definition: str | None = Field(default=None, max_length=1000)
    synonyms: list[str] = Field(default_factory=list, max_length=10)
    options: list[GlossaryOption] = Field(default_factory=list, max_length=4)


class SchemaOut(BaseModel):
    connection: ConnectionOut
    tables: list[TableOut]
    glossary: list[GlossaryTermIO]
    max_rows: int
    statement_timeout_ms: int


class ChoiceIn(BaseModel):
    term: str = Field(min_length=1, max_length=80)
    option_id: str | None = Field(default=None, max_length=40)
    custom_definition: str | None = Field(default=None, max_length=500)


class RepairIn(BaseModel):
    """Ask the model to fix a query the database rejected (one user-triggered attempt)."""

    sql: str = Field(min_length=1, max_length=10_000)
    error: str = Field(min_length=1, max_length=1000)


class SqlQueryIn(BaseModel):
    connection_id: uuid.UUID
    question: str = Field(min_length=1, max_length=1000)
    clarification_context: list[ChoiceIn] = Field(default_factory=list, max_length=5)
    repair: RepairIn | None = None

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class ClarificationOut(BaseModel):
    term: str
    question: str
    options: list[GlossaryOption]
    source: Literal["glossary", "model"]


class SqlAnswerOut(BaseModel):
    query_id: uuid.UUID
    status: Literal["clarification_required", "executed", "rejected", "failed", "unsupported"]
    question: str
    clarification: ClarificationOut | None = None
    sql: str | None = None
    explanation: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    definitions_used: list[dict[str, str]] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int | None = None
    truncated: bool = False
    duration_ms: int | None = None
    generation_ms: int | None = None
    message: str | None = None
    # True when the database rejected a validated query (e.g. a misspelled column): the UI can
    # offer one "ask the model to fix it" turn. Never for safety rejections.
    repairable: bool = False
    model: str | None = None
    prompt_version: str = "sql-v3"
    read_only: bool = True
    database: str | None = None


class HistoryItem(BaseModel):
    id: uuid.UUID
    question: str
    status: str
    row_count: int | None
    created_at: datetime
