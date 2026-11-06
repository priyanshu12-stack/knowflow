"""TRD §10 / PRD §9 SQL safety: AST validation rejects anything that isn't one safe SELECT."""

import pytest

from app.modules.sql_assistant.assistant import (
    Choice,
    GlossaryEntry,
    pending_clarification,
    resolved_definitions,
)
from app.modules.sql_assistant.validation import SqlRejectedError, redact_literals, validate_sql

SCHEMAS = ["sales"]


def ok(sql: str, max_rows: int = 500) -> str:
    return validate_sql(sql, allowed_schemas=SCHEMAS, max_rows=max_rows).sql


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("select * from customers", "SELECT * FROM sales.customers LIMIT 501"),
        ("select id from sales.orders limit 10", "SELECT id FROM sales.orders LIMIT 10"),
        ("select id from sales.orders limit 9999", "SELECT id FROM sales.orders LIMIT 501"),
        (
            "with t as (select customer_id from orders) select count(*) from t",
            "WITH t AS (SELECT customer_id FROM sales.orders) SELECT COUNT(*) FROM t LIMIT 501",
        ),
        (
            "select 1 union all select 2",
            "SELECT * FROM (SELECT 1 UNION ALL SELECT 2) AS q LIMIT 501",
        ),
        ("SELECT name FROM customers;", "SELECT name FROM sales.customers LIMIT 501"),
    ],
)
def test_safe_selects_are_qualified_and_capped(sql: str, expected: str) -> None:
    assert ok(sql) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET name = 'x'",
        "INSERT INTO customers (id) VALUES (1)",
        "MERGE INTO customers c USING orders o ON c.id = o.customer_id WHEN MATCHED THEN DELETE",
        "DROP TABLE customers",
        "TRUNCATE customers",
        "ALTER TABLE customers ADD COLUMN x int",
        "CREATE TABLE x (a int)",
        "GRANT SELECT ON customers TO PUBLIC",
        "COPY customers TO '/tmp/x'",
        "SET statement_timeout = 0",
        "BEGIN",
        "EXPLAIN ANALYZE SELECT 1",
        "select 1; select 2",
        "select 1; drop table customers",
        "with x as (delete from customers returning *) select * from x",
        "select * into backup from customers",
        "select * from customers for update",
        "select * from pg_catalog.pg_roles",
        "select * from pg_user",
        "select * from information_schema.columns",
        "select * from public.documents",
        "select * from otherdb.sales.customers",
        "select pg_sleep(30)",
        "select pg_read_file('/etc/passwd')",
        "select lo_import('/etc/passwd')",
        "select dblink('host=x', 'select 1')",
        "select current_setting('data_directory')",
        "select set_config('statement_timeout', '0', false)",
        "select nextval('seq')",
        "select * from generate_series(1, 1000000000)",
        "select * from customers limit (select 1)",
        "select * from customers c join pg_catalog.pg_shadow s on true",
        "",
        "not sql at all )(",
    ],
)
def test_unsafe_sql_is_rejected(sql: str) -> None:
    with pytest.raises(SqlRejectedError):
        validate_sql(sql, allowed_schemas=SCHEMAS, max_rows=500)


def test_reason_is_specific() -> None:
    with pytest.raises(SqlRejectedError, match="Exactly one statement"):
        validate_sql("select 1; select 2", allowed_schemas=SCHEMAS, max_rows=5)
    with pytest.raises(SqlRejectedError, match="Schema 'public'"):
        validate_sql("select * from public.t", allowed_schemas=SCHEMAS, max_rows=5)
    with pytest.raises(SqlRejectedError, match="pg_sleep"):
        validate_sql("select pg_sleep(1)", allowed_schemas=SCHEMAS, max_rows=5)


def test_literals_are_redacted_for_history() -> None:
    assert redact_literals("select * from sales.customers where email = 'a@b.c' and id = 3") == (
        "SELECT * FROM sales.customers WHERE email = '?' AND id = 3"
    )


GLOSSARY = [
    GlossaryEntry(
        "best customer",
        "ambiguous",
        synonyms=["top customer"],
        options=[
            {"id": "paid_revenue", "label": "Revenue", "definition": "SUM(payments.amount)"},
            {"id": "order_count", "label": "Orders", "definition": "COUNT(paid orders)"},
        ],
    ),
    GlossaryEntry("revenue", "definition", definition="SUM(payments.amount)"),
]


def test_ambiguous_term_requires_a_choice_including_plurals_and_synonyms() -> None:
    assert pending_clarification("Show me our best customers last month", GLOSSARY, []) is not None
    assert pending_clarification("Who are the TOP CUSTOMERS?", GLOSSARY, []) is not None
    assert pending_clarification("How many orders last week?", GLOSSARY, []) is None
    chosen = [Choice("best customer", option_id="paid_revenue")]
    assert pending_clarification("best customers last month", GLOSSARY, chosen) is None


def test_definitions_include_the_choice_and_matching_glossary_terms() -> None:
    defs = resolved_definitions(
        "best customers by revenue", GLOSSARY, [Choice("best customer", option_id="order_count")]
    )
    assert ("best customer", "COUNT(paid orders)") in defs
    assert ("revenue", "SUM(payments.amount)") in defs
    custom = resolved_definitions(
        "best customers", GLOSSARY, [Choice("best customer", custom_definition="most refunds")]
    )
    assert custom == [("best customer", "most refunds")]
