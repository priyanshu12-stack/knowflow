"""Connecting to an analysed database: read-only checks, schema introspection, execution.

Execution layers (TRD §10), on top of the AST validator:
- the connection's role must not be a superuser and must have no write privilege on the
  allow-listed tables (checked when the connection is saved and before each query);
- every query runs in a `READ ONLY` transaction with `SET LOCAL statement_timeout` and
  `lock_timeout`;
- results are capped at `max_rows` (+1 to detect truncation) and never streamed unbounded.
"""

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from app.core.errors import AppError


@dataclass(frozen=True)
class Target:
    host: str
    port: int
    database: str
    username: str
    password: str


@lru_cache(maxsize=8)
def _engine(host: str, port: int, database: str, username: str, password: str) -> Engine:
    url = URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "application_name": "knowflow-sql-analyst"},
    )


def engine_for(t: Target) -> Engine:
    return _engine(t.host, t.port, t.database, t.username, t.password)


def _connection_error(exc: Exception) -> AppError:
    # Never echo the driver message: it can contain host, user or password hints.
    return AppError(
        "sql_connection_failed",
        "Couldn't connect with these settings. Check host, port, database, user and password.",
        422,
    )


@dataclass
class ReadOnlyCheck:
    server_version: str
    is_superuser: bool
    writable_tables: list[str]
    read_only_default: bool


def check_read_only(t: Target, schemas: list[str]) -> ReadOnlyCheck:
    try:
        with engine_for(t).connect() as conn:
            version = str(conn.scalar(text("SHOW server_version")))
            superuser = bool(
                conn.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
            )
            writable = list(
                conn.scalars(
                    text(
                        "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                        "WHERE table_schema = ANY(:s) AND ("
                        "has_table_privilege(quote_ident(table_schema) || '.' || "
                        "quote_ident(table_name), 'INSERT') OR "
                        "has_table_privilege(quote_ident(table_schema) || '.' || "
                        "quote_ident(table_name), 'UPDATE') OR "
                        "has_table_privilege(quote_ident(table_schema) || '.' || "
                        "quote_ident(table_name), 'DELETE'))"
                    ),
                    {"s": schemas},
                )
            )
            ro_default = str(conn.scalar(text("SHOW default_transaction_read_only"))) == "on"
    except (OperationalError, DBAPIError) as exc:
        raise _connection_error(exc) from exc
    return ReadOnlyCheck(version, superuser, writable, ro_default)


def require_read_only(check: ReadOnlyCheck) -> None:
    if check.is_superuser:
        raise AppError(
            "sql_role_not_read_only",
            "This user is a superuser. Connect with a role that can only SELECT.",
            422,
        )
    if check.writable_tables:
        raise AppError(
            "sql_role_not_read_only",
            "This user can write to "
            + ", ".join(check.writable_tables[:5])
            + ". Connect with a role that has SELECT privileges only.",
            422,
        )


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool
    description: str | None


@dataclass
class Table:
    schema: str
    name: str
    description: str | None
    columns: list[Column]
    # "column -> schema.table.column" join hints from foreign keys
    references: list[str] = field(default_factory=list)


def introspect(t: Target, schemas: list[str]) -> list[Table]:
    """Allow-listed schemas only: tables, columns, types and comments. No data is read."""
    try:
        with engine_for(t).connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT c.table_schema, c.table_name, c.column_name, c.data_type, "
                    "c.is_nullable = 'YES', "
                    "col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))"
                    "::regclass, c.ordinal_position), "
                    "obj_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))"
                    "::regclass, 'pg_class') "
                    "FROM information_schema.columns c "
                    "JOIN information_schema.tables t USING (table_schema, table_name) "
                    "WHERE c.table_schema = ANY(:s) AND t.table_type IN ('BASE TABLE', 'VIEW') "
                    "ORDER BY c.table_schema, c.table_name, c.ordinal_position"
                ),
                {"s": schemas},
            ).all()
            # Foreign keys as join hints (pg_constraint: works without information_schema
            # privileges on the referenced table).
            fks = conn.execute(
                text(
                    "SELECT ns.nspname, cl.relname, a.attname, "
                    "rns.nspname || '.' || rcl.relname || '.' || ra.attname "
                    "FROM pg_constraint co "
                    "JOIN pg_class cl ON cl.oid = co.conrelid "
                    "JOIN pg_namespace ns ON ns.oid = cl.relnamespace "
                    "JOIN pg_class rcl ON rcl.oid = co.confrelid "
                    "JOIN pg_namespace rns ON rns.oid = rcl.relnamespace "
                    "JOIN pg_attribute a ON a.attrelid = co.conrelid AND a.attnum = co.conkey[1] "
                    "JOIN pg_attribute ra ON ra.attrelid = co.confrelid "
                    "AND ra.attnum = co.confkey[1] "
                    "WHERE co.contype = 'f' AND ns.nspname = ANY(:s)"
                ),
                {"s": schemas},
            ).all()
    except (OperationalError, DBAPIError) as exc:
        raise _connection_error(exc) from exc
    tables: dict[tuple[str, str], Table] = {}
    for schema, table, column, dtype, nullable, col_desc, tbl_desc in rows:
        key = (schema, table)
        if key not in tables:
            tables[key] = Table(schema, table, tbl_desc, [])
        tables[key].columns.append(Column(column, dtype, bool(nullable), col_desc))
    for schema, table, column, ref in fks:
        if (schema, table) in tables:
            tables[(schema, table)].references.append(f"{column} -> {ref}")
    return list(tables.values())


def schema_prompt(tables: list[Table]) -> str:
    """Compact schema description for the model: names, types, comments. Never credentials."""
    lines = []
    for t in tables:
        lines.append(
            f"TABLE {t.schema}.{t.name}" + (f" -- {t.description}" if t.description else "")
        )
        for c in t.columns:
            note = f" -- {c.description}" if c.description else ""
            lines.append(f"  {c.name} {c.data_type}{' NULL' if c.nullable else ''}{note}")
        for ref in t.references:
            lines.append(f"  JOIN: {t.schema}.{t.name}.{ref}")
    return "\n".join(lines)


def _json_value(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, bytes | memoryview):
        return "<binary>"
    return v


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    duration_ms: int


def execute(
    t: Target, sql: str, *, max_rows: int, statement_timeout_ms: int, lock_timeout_ms: int
) -> QueryResult:
    started = time.perf_counter()
    try:
        with engine_for(t).connect() as conn:
            # psycopg has already opened the transaction implicitly; this must be its first
            # statement (a second BEGIN would only warn and not apply READ ONLY).
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = {int(statement_timeout_ms)}"))
            conn.execute(text(f"SET LOCAL lock_timeout = {int(lock_timeout_ms)}"))
            result = conn.execute(text(sql))
            columns = list(result.keys())
            fetched = result.fetchmany(max_rows + 1)
            conn.rollback()
    except DBAPIError as exc:
        message = (
            str(getattr(exc, "orig", "")).splitlines()[0] if getattr(exc, "orig", None) else ""
        )
        if "statement timeout" in message:
            raise AppError(
                "sql_timeout",
                f"The query took longer than {statement_timeout_ms / 1000:g} seconds and was "
                "stopped. Try a narrower question (fewer rows or a shorter period).",
                422,
            ) from exc
        if "read-only transaction" in message or "permission denied" in message:
            raise AppError(
                "sql_rejected", "The database refused the query: it isn't read-only.", 422
            ) from exc
        # Postgres errors on a validated SELECT are about the query itself (unknown column, type
        # mismatch). They contain no credentials, so the first line is useful and safe to show.
        raise AppError(
            "sql_execution_failed", f"The database couldn't run the query: {message}", 422
        ) from exc
    except SQLAlchemyError as exc:
        raise _connection_error(exc) from exc
    return QueryResult(
        columns=columns,
        rows=[[_json_value(v) for v in row] for row in fetched[:max_rows]],
        truncated=len(fetched) > max_rows,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
