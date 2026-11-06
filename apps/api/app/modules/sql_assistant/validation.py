"""SQL safety validation with SQLGlot's AST (TRD §6.3, §10, ADR-006). Regex is never used.

A query is accepted only if ALL of these hold:
1. It parses as exactly one PostgreSQL statement.
2. The root is a SELECT or a set operation of SELECTs (UNION / INTERSECT / EXCEPT), optionally
   with CTEs (WITH ... SELECT).
3. No node anywhere in the tree writes, changes schema, locks, controls transactions or runs a
   command: INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, ALTER, TRUNCATE, COPY, GRANT, SET,
   SELECT INTO, FOR UPDATE/SHARE, unknown commands.
4. Every table is either a CTE defined in the query or lives in an allow-listed schema. System
   catalogs (pg_catalog, information_schema, pg_*) and cross-database names are rejected.
5. No dangerous function is called (sleep, file / large-object access, dblink, settings,
   backend control, ...).
Accepted queries get a row cap (LIMIT max_rows + 1, so truncation is detectable).

The read-only database role, statement timeout and lock timeout are separate layers
(execution.py); this validator must reject unsafe SQL even if those were misconfigured.
"""

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWED_ROOTS: tuple[type[exp.Expression], ...] = (exp.Select, exp.Union, exp.Intersect, exp.Except)

_FORBIDDEN_NAMES = (
    "Insert",
    "Update",
    "Delete",
    "Merge",
    "Create",
    "Drop",
    "Alter",
    "AlterTable",
    "TruncateTable",
    "Command",
    "Copy",
    "Grant",
    "Revoke",
    "Set",
    "SetItem",
    "Use",
    "Transaction",
    "Commit",
    "Rollback",
    "Into",
    "Lock",
    "LoadData",
    "Pragma",
    "Cache",
    "Uncache",
    "Refresh",
    "Analyze",
    "Comment",
    "Kill",
    "Describe",
    "Show",
    "Execute",
    "Call",
)
# Not every class exists in every sqlglot version; resolve the ones that do.
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = tuple(
    getattr(exp, name) for name in _FORBIDDEN_NAMES if isinstance(getattr(exp, name, None), type)
)

DANGEROUS_FUNCTIONS = {
    "pg_sleep",
    "pg_sleep_for",
    "pg_sleep_until",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "set_config",
    "current_setting",
    "lo_import",
    "lo_export",
    "lo_get",
    "lo_put",
    "lo_from_bytea",
    "dblink",
    "dblink_exec",
    "dblink_connect",
    "query_to_xml",
    "table_to_xml",
    "database_to_xml",
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "txid_current",
    "nextval",
    "setval",
    "currval",
    "pg_logical_emit_message",
    "version",
    "inet_server_addr",
    "current_user",
    "session_user",
    "pg_backend_pid",
}
DANGEROUS_PREFIXES = ("pg_", "lo_", "dblink", "xpath")
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


class SqlRejectedError(Exception):
    def __init__(self, reason: str, code: str = "sql_rejected") -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


@dataclass
class ValidatedQuery:
    sql: str  # normalised, schema-qualified, row-capped SQL that will be executed
    tables: list[str] = field(default_factory=list)
    capped_at: int = 0


def _function_name(node: object) -> str | None:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    if isinstance(node, exp.Func):
        return node.sql_name().lower()
    return None


def validate_sql(sql: str, *, allowed_schemas: list[str], max_rows: int) -> ValidatedQuery:
    if not allowed_schemas:
        raise SqlRejectedError("No schemas are allowed for this connection.")
    text = sql.strip()
    if not text:
        raise SqlRejectedError("The query is empty.")
    if len(text) > 10_000:
        raise SqlRejectedError("The query is too long.")
    try:
        statements = [s for s in sqlglot.parse(text, read="postgres") if s is not None]
    except ParseError as exc:
        raise SqlRejectedError(
            "The query couldn't be parsed as PostgreSQL.", "sql_parse_error"
        ) from exc
    if len(statements) != 1:
        raise SqlRejectedError("Exactly one statement is allowed; multiple statements were found.")
    tree = statements[0]
    if not isinstance(tree, ALLOWED_ROOTS):
        raise SqlRejectedError(f"Only SELECT queries are allowed (got {tree.key.upper()}).")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    allowed = {s.lower() for s in allowed_schemas}
    default_schema = allowed_schemas[0]
    tables: list[str] = []

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejectedError(f"{node.key.upper()} is not allowed in a read-only query.")
        name = _function_name(node)
        if name and (name in DANGEROUS_FUNCTIONS or name.startswith(DANGEROUS_PREFIXES)):
            raise SqlRejectedError(f"The function {name}() is not allowed.")
        if isinstance(node, exp.Table):
            table = node.name.lower()
            schema = (node.db or "").lower()
            if node.catalog:
                raise SqlRejectedError("Cross-database references are not allowed.")
            if not table:
                raise SqlRejectedError("Table functions and dynamic table names are not allowed.")
            if not schema and table in cte_names:
                continue
            if schema in SYSTEM_SCHEMAS or table.startswith("pg_"):
                raise SqlRejectedError("System catalogs can't be queried.")
            if not schema:
                node.set("db", exp.to_identifier(default_schema))
                schema = default_schema.lower()
            if schema not in allowed:
                raise SqlRejectedError(f"Schema '{schema}' is not in the allowed list.")
            tables.append(f"{schema}.{table}")

    cap = max_rows + 1
    if isinstance(tree, exp.Select):
        limit = tree.args.get("limit")
        current = None
        if limit is not None:
            value = limit.expression if isinstance(limit, exp.Limit) else limit
            try:
                current = int(value.name) if isinstance(value, exp.Literal) else None
            except ValueError:
                current = None
            if current is None:
                raise SqlRejectedError("LIMIT must be a plain number.")
        tree = tree.limit(min(current, cap) if current is not None else cap)
    else:
        tree = (
            exp.select("*")
            .from_(exp.Subquery(this=tree, alias=exp.TableAlias(this=exp.to_identifier("q"))))
            .limit(cap)
        )

    return ValidatedQuery(
        sql=tree.sql(dialect="postgres"), tables=sorted(set(tables)), capped_at=max_rows
    )


def redact_literals(sql: str) -> str:
    """Replace string literals with '?' before storing SQL in history (TRD §10)."""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except ParseError:
        return "<unparseable query>"
    for lit in list(tree.find_all(exp.Literal)):
        if lit.is_string:
            lit.replace(exp.Literal.string("?"))
    return tree.sql(dialect="postgres")
