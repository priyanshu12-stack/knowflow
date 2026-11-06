"""SQL Analyst use cases: connections, schema, glossary, questions and history (PRD §5.5)."""

import logging
import time
import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import SqlConnection, SqlGlossaryTerm, SqlQueryLog
from app.modules.models.gate import generation_slot
from app.modules.models.interfaces import ChatModel, ModelError
from app.modules.sql_assistant import database as db
from app.modules.sql_assistant import secrets
from app.modules.sql_assistant.assistant import (
    PROMPT_VERSION,
    Choice,
    GlossaryEntry,
    Repair,
    generate,
    pending_clarification,
    resolved_definitions,
)
from app.modules.sql_assistant.validation import SqlRejectedError, redact_literals, validate_sql
from app.schemas.sql import (
    ClarificationOut,
    ColumnOut,
    ConnectionIn,
    ConnectionOut,
    GlossaryOption,
    GlossaryTermIO,
    HistoryItem,
    SchemaOut,
    SqlAnswerOut,
    SqlQueryIn,
    TableOut,
)

logger = logging.getLogger(__name__)

DEMO_NAME = "Demo sales (synthetic)"

# Visible, user-editable definitions (TRD §10 "semantic glossary").
DEFAULT_GLOSSARY: list[GlossaryTermIO] = [
    GlossaryTermIO(
        term="best customer",
        kind="ambiguous",
        synonyms=["top customer", "most valuable customer", "biggest customer"],
        options=[
            GlossaryOption(
                id="paid_revenue",
                label="Highest paid revenue",
                definition="Rank customers by net paid revenue: SUM(sales.payments.amount) "
                "(payments minus refunds) over their orders.",
            ),
            GlossaryOption(
                id="order_count",
                label="Most orders",
                definition="Rank customers by the number of orders with status 'paid'.",
            ),
            GlossaryOption(
                id="avg_order_value",
                label="Highest average order value",
                definition="Rank customers by AVG(sales.orders.total_amount) over orders with "
                "status 'paid'.",
            ),
        ],
    ),
    GlossaryTermIO(
        term="top product",
        kind="ambiguous",
        synonyms=["best product", "best-selling product", "best selling product"],
        options=[
            GlossaryOption(
                id="units",
                label="Most units sold",
                definition="Rank products by SUM(sales.order_items.quantity) on paid orders.",
            ),
            GlossaryOption(
                id="revenue",
                label="Highest revenue",
                definition="Rank products by SUM(quantity * unit_price) on paid orders.",
            ),
        ],
    ),
    GlossaryTermIO(
        term="revenue",
        kind="definition",
        synonyms=["sales", "income"],
        definition="Net paid revenue = SUM(sales.payments.amount): payments are positive, "
        "refunds negative. Cancelled and pending orders have no payments.",
    ),
    GlossaryTermIO(
        term="active customer",
        kind="definition",
        definition="A customer with at least one order with status 'paid' in the last 90 days.",
    ),
    GlossaryTermIO(
        term="refund rate",
        kind="definition",
        definition="Orders with status 'refunded' divided by orders with status 'paid' or "
        "'refunded', in the same period.",
    ),
]


def connection_out(c: SqlConnection) -> ConnectionOut:
    return ConnectionOut(
        id=c.id,
        display_name=c.display_name,
        db_type=c.db_type,
        host=c.host,
        port=c.port,
        database_name=c.database_name,
        username=c.username,
        allowed_schemas=c.allowed_schemas,
        is_demo=c.is_demo,
        created_at=c.created_at,
    )


def _target(settings: Settings, c: SqlConnection) -> db.Target:
    return db.Target(
        c.host,
        c.port,
        c.database_name,
        c.username,
        secrets.decrypt(settings, c.encrypted_secret_ref),
    )


def _replace_glossary(
    session: Session, connection_id: uuid.UUID, terms: list[GlossaryTermIO]
) -> None:
    session.execute(delete(SqlGlossaryTerm).where(SqlGlossaryTerm.connection_id == connection_id))
    seen: set[str] = set()
    for t in terms:
        key = t.term.strip().lower()
        if key in seen:
            raise AppError("glossary_duplicate", f"The term “{t.term}” appears twice.", 422)
        seen.add(key)
        if t.kind == "ambiguous" and not 2 <= len(t.options) <= 4:
            raise AppError("glossary_invalid", f"Ambiguous term “{t.term}” needs 2-4 options.", 422)
        if t.kind == "definition" and not (t.definition or "").strip():
            raise AppError("glossary_invalid", f"Term “{t.term}” needs a definition.", 422)
        session.add(
            SqlGlossaryTerm(
                connection_id=connection_id,
                term=t.term.strip(),
                kind=t.kind,
                definition=t.definition,
                synonyms=[s.strip() for s in t.synonyms if s.strip()],
                options=[o.model_dump() for o in t.options],
            )
        )


def ensure_demo_connection(session: Session, settings: Settings, workspace_id: uuid.UUID) -> None:
    """Register the seeded demo database once it exists (scripts: dev.ps1 seed-demo)."""
    password = settings.demo_db_reader_password.get_secret_value()
    if not password:
        return
    exists = session.scalar(
        select(SqlConnection.id).where(
            SqlConnection.workspace_id == workspace_id, SqlConnection.is_demo
        )
    )
    if exists:
        return
    conn = SqlConnection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        display_name=DEMO_NAME,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database_name=settings.demo_db_name,
        username=settings.demo_reader_user,
        encrypted_secret_ref=secrets.encrypt(settings, password),
        allowed_schemas=["sales"],
        is_demo=True,
    )
    session.add(conn)
    session.flush()
    _replace_glossary(session, conn.id, DEFAULT_GLOSSARY)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def list_connections(
    session: Session, settings: Settings, workspace_id: uuid.UUID
) -> list[ConnectionOut]:
    ensure_demo_connection(session, settings, workspace_id)
    rows = session.scalars(
        select(SqlConnection)
        .where(SqlConnection.workspace_id == workspace_id)
        .order_by(SqlConnection.is_demo.desc(), SqlConnection.created_at)
    ).all()
    return [connection_out(c) for c in rows]


def get_connection(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> SqlConnection:
    c = session.scalar(
        select(SqlConnection).where(
            SqlConnection.id == cid, SqlConnection.workspace_id == workspace_id
        )
    )
    if c is None:
        raise AppError("connection_not_found", "This database connection doesn't exist.", 404)
    return c


def test_and_save(
    session: Session, settings: Settings, workspace_id: uuid.UUID, body: ConnectionIn
) -> ConnectionOut:
    """TRD §8 /sql/connections/test: connect, prove the role is read-only, then save."""
    target = db.Target(
        body.host, body.port, body.database_name, body.username, body.password.get_secret_value()
    )
    check = db.check_read_only(target, body.allowed_schemas)
    db.require_read_only(check)
    tables = db.introspect(target, body.allowed_schemas)
    if not tables:
        raise AppError(
            "sql_no_tables",
            "No tables are visible to this user in the allowed schemas.",
            422,
        )
    conn = SqlConnection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        display_name=body.display_name.strip(),
        host=body.host,
        port=body.port,
        database_name=body.database_name,
        username=body.username,
        encrypted_secret_ref=secrets.encrypt(settings, body.password.get_secret_value()),
        allowed_schemas=body.allowed_schemas,
    )
    session.add(conn)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "connection_exists", "A connection with this name already exists.", 409
        ) from exc
    logger.info(
        "sql_connection_saved", extra={"connection_id": str(conn.id), "tables": len(tables)}
    )
    return connection_out(conn)


def delete_connection(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> None:
    try:
        c = get_connection(session, workspace_id, cid)
    except AppError:
        return
    if c.is_demo:
        raise AppError("connection_is_demo", "The demo connection can't be removed.", 409)
    session.delete(c)
    session.commit()


def glossary(session: Session, cid: uuid.UUID) -> list[GlossaryTermIO]:
    rows = session.scalars(
        select(SqlGlossaryTerm)
        .where(SqlGlossaryTerm.connection_id == cid)
        .order_by(SqlGlossaryTerm.term)
    ).all()
    return [
        GlossaryTermIO(
            term=r.term,
            kind=r.kind,
            definition=r.definition,
            synonyms=r.synonyms,
            options=[GlossaryOption.model_validate(o) for o in r.options],
        )
        for r in rows
    ]


def save_glossary(
    session: Session, workspace_id: uuid.UUID, cid: uuid.UUID, terms: list[GlossaryTermIO]
) -> list[GlossaryTermIO]:
    get_connection(session, workspace_id, cid)
    _replace_glossary(session, cid, terms)
    session.commit()
    return glossary(session, cid)


def schema(
    session: Session, settings: Settings, workspace_id: uuid.UUID, cid: uuid.UUID
) -> SchemaOut:
    c = get_connection(session, workspace_id, cid)
    tables = db.introspect(_target(settings, c), c.allowed_schemas)
    return SchemaOut(
        connection=connection_out(c),
        tables=[
            TableOut(
                schema_name=t.schema,
                name=t.name,
                description=t.description,
                columns=[ColumnOut(**col.__dict__) for col in t.columns],
            )
            for t in tables
        ],
        glossary=glossary(session, cid),
        max_rows=settings.sql_max_rows,
        statement_timeout_ms=settings.sql_statement_timeout_ms,
    )


def _entries(terms: list[GlossaryTermIO]) -> list[GlossaryEntry]:
    return [
        GlossaryEntry(t.term, t.kind, t.definition, t.synonyms, [o.model_dump() for o in t.options])
        for t in terms
    ]


def _log(
    session: Session,
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    answer: SqlAnswerOut,
    decision: dict[str, object],
) -> SqlAnswerOut:
    row = SqlQueryLog(
        id=answer.query_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        question=answer.question,
        status=answer.status,
        clarification=answer.clarification.model_dump() if answer.clarification else None,
        sql_redacted=redact_literals(answer.sql) if answer.sql else None,
        decision=decision,
        row_count=answer.row_count,
        duration_ms=answer.duration_ms,
    )
    session.add(row)
    session.commit()
    logger.info(
        "sql_question",
        extra={
            "query_id": str(answer.query_id),
            "status": answer.status,
            "rows": answer.row_count,
            "duration_ms": answer.duration_ms,
            "question_chars": len(answer.question),
        },
    )
    return answer


def ask(
    session: Session, settings: Settings, workspace_id: uuid.UUID, body: SqlQueryIn, chat: ChatModel
) -> SqlAnswerOut:
    c = get_connection(session, workspace_id, body.connection_id)
    terms = glossary(session, c.id)
    entries = _entries(terms)
    choices = [Choice(x.term, x.option_id, x.custom_definition) for x in body.clarification_context]
    base = SqlAnswerOut(
        query_id=uuid.uuid4(),
        status="failed",
        question=body.question,
        database=c.database_name,
        model=chat.name,
        prompt_version=PROMPT_VERSION,
    )

    # 1. Deterministic clarification from the glossary: no model call, nothing executed.
    pending = pending_clarification(body.question, entries, choices)
    if pending is not None:
        base.status = "clarification_required"
        base.clarification = ClarificationOut(
            term=pending.term,
            question=f"What should “{pending.term}” mean for this question?",
            options=[GlossaryOption.model_validate(o) for o in pending.options],
            source="glossary",
        )
        return _log(session, workspace_id, c.id, base, {"stage": "glossary", "term": pending.term})

    target = _target(settings, c)
    db.require_read_only(db.check_read_only(target, c.allowed_schemas))
    tables = db.introspect(target, c.allowed_schemas)
    definitions = resolved_definitions(body.question, entries, choices)
    base.definitions_used = [{"term": t, "definition": d} for t, d in definitions]

    # 2. Model: SQL, its own clarification, or unsupported.
    try:
        with generation_slot(settings):
            out, gen_ms = generate(
                chat,
                body.question,
                db.schema_prompt(tables),
                definitions,
                # Local date: "last month" means the user's calendar month, not UTC's.
                datetime.now().astimezone().date(),
                Repair(body.repair.sql, body.repair.error) if body.repair else None,
            )
    except ModelError as exc:
        raise AppError(exc.code, exc.message, 503 if exc.retryable else 502) from exc
    base.generation_ms = gen_ms
    base.explanation, base.assumptions = out.explanation or None, out.assumptions

    if out.status == "clarification_required" and out.clarification is not None:
        base.status = "clarification_required"
        base.clarification = ClarificationOut(
            term=out.clarification.missing_concept or "this term",
            question=out.clarification.question,
            options=[
                GlossaryOption(id=f"opt{i}", label=o.label, definition=o.definition)
                for i, o in enumerate(out.clarification.options, start=1)
            ],
            source="model",
        )
        return _log(session, workspace_id, c.id, base, {"stage": "model_clarification"})
    if out.status == "unsupported":
        base.status = "unsupported"
        base.message = out.reason or "This question can't be answered from the allowed tables."
        return _log(session, workspace_id, c.id, base, {"stage": "model_unsupported"})

    # 3. Validate. Rejected SQL is shown (for transparency) but never executed.
    base.sql = out.sql
    try:
        validated = validate_sql(
            out.sql or "", allowed_schemas=c.allowed_schemas, max_rows=settings.sql_max_rows
        )
    except SqlRejectedError as exc:
        base.status = "rejected"
        base.message = f"The generated SQL was rejected and not run: {exc.reason}"
        return _log(
            session, workspace_id, c.id, base, {"stage": "validation", "reason": exc.reason}
        )
    base.sql, base.tables = validated.sql, validated.tables

    # 4. Execute read-only.
    started = time.perf_counter()
    try:
        result = db.execute(
            target,
            validated.sql,
            max_rows=settings.sql_max_rows,
            statement_timeout_ms=settings.sql_statement_timeout_ms,
            lock_timeout_ms=settings.sql_lock_timeout_ms,
        )
    except AppError as exc:
        base.status = "failed"
        base.message = exc.message
        # Query errors (unknown column, type mismatch) can be repaired once; timeouts and
        # safety refusals can't.
        base.repairable = exc.code == "sql_execution_failed" and body.repair is None
        base.duration_ms = round((time.perf_counter() - started) * 1000)
        return _log(session, workspace_id, c.id, base, {"stage": "execution", "code": exc.code})
    base.status = "executed"
    base.columns, base.rows = result.columns, result.rows
    base.row_count, base.truncated, base.duration_ms = (
        len(result.rows),
        result.truncated,
        result.duration_ms,
    )
    return _log(session, workspace_id, c.id, base, {"stage": "executed", "validated": True})


def history(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> list[HistoryItem]:
    rows = session.scalars(
        select(SqlQueryLog)
        .where(SqlQueryLog.workspace_id == workspace_id, SqlQueryLog.connection_id == cid)
        .order_by(SqlQueryLog.created_at.desc())
        .limit(50)
    ).all()
    return [
        HistoryItem(
            id=r.id,
            question=r.question,
            status=r.status,
            row_count=r.row_count,
            created_at=r.created_at,
        )
        for r in rows
    ]
