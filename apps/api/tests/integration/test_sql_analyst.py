"""M6 exit: an ambiguous question asks for clarification, unsafe SQL is rejected, and a safe
SELECT returns a table. Runs against a throwaway seeded demo database with its own reader role."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from app.core.config import Settings, get_settings
from app.modules.sql_assistant import demo
from tests.fake_ollama import FakeOllama

pytestmark = pytest.mark.integration

READER_PASSWORD = "test-reader-password-123"


@pytest.fixture(scope="module")
def demo_settings() -> Iterator[Settings]:
    base = get_settings()
    settings = base.model_copy(
        update={
            "demo_db_name": "knowflow_demo_test",
            "demo_reader_user": "knowflow_reader_test",
            "demo_db_reader_password": SecretStr(READER_PASSWORD),
            "sql_statement_timeout_ms": 500,
            "sql_max_rows": 50,
        }
    )
    demo.seed(settings)
    yield settings
    admin = create_engine(base.database_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text('DROP DATABASE IF EXISTS "knowflow_demo_test" WITH (FORCE)'))
        conn.execute(text('DROP ROLE IF EXISTS "knowflow_reader_test"'))
    admin.dispose()


@pytest.fixture
def sql_client(
    db_client: TestClient, demo_settings: Settings, fake_ollama: FakeOllama, tmp_path: Any
) -> Iterator[TestClient]:
    s = demo_settings.model_copy(update={"secret_key_file": tmp_path / "secret.key"})
    db_client.app.dependency_overrides[get_settings] = lambda: s  # type: ignore[attr-defined]
    yield db_client
    db_client.app.dependency_overrides.pop(get_settings, None)  # type: ignore[attr-defined]


def demo_id(client: TestClient) -> str:
    conns = client.get("/api/v1/sql/connections").json()
    demo_conn = next(c for c in conns if c["is_demo"])
    assert "password" not in json.dumps(conns).lower()
    assert "encrypted" not in json.dumps(conns).lower()
    return str(demo_conn["id"])


def model_sql(fake: FakeOllama, sql: str, **extra: Any) -> None:
    fake.chat_replies.append(
        json.dumps(
            {
                "status": "ready",
                "sql": sql,
                "explanation": "Computes it.",
                "assumptions": [],
                "tables": [],
                **extra,
            }
        )
    )


def ask(
    client: TestClient, cid: str, question: str, choices: list[dict[str, str]] | None = None
) -> Any:
    r = client.post(
        "/api/v1/sql/query",
        json={"connection_id": cid, "question": question, "clarification_context": choices or []},
    )
    assert r.status_code == 200, r.text
    return r.json()


def chat_calls(fake: FakeOllama) -> int:
    return sum(1 for p, _ in fake.requests if p == "/api/chat")


def test_demo_connection_schema_and_glossary(sql_client: TestClient) -> None:
    cid = demo_id(sql_client)
    schema = sql_client.get(f"/api/v1/sql/schema/{cid}").json()
    names = {t["name"] for t in schema["tables"]}
    assert names == {"customers", "products", "orders", "order_items", "payments"}
    payments = next(t for t in schema["tables"] if t["name"] == "payments")
    assert "refund" in payments["description"].lower()
    assert any(
        g["term"] == "best customer" and g["kind"] == "ambiguous" for g in schema["glossary"]
    )
    assert schema["max_rows"] == 50


def test_journey_c_best_customers_asks_first_then_runs(
    sql_client: TestClient, fake_ollama: FakeOllama
) -> None:
    cid = demo_id(sql_client)
    before = chat_calls(fake_ollama)
    first = ask(sql_client, cid, "Show me our best customers last month.")
    assert first["status"] == "clarification_required"
    assert first["sql"] is None and first["rows"] == []
    labels = [o["label"] for o in first["clarification"]["options"]]
    assert labels == ["Highest paid revenue", "Most orders", "Highest average order value"]
    assert chat_calls(fake_ollama) == before  # nothing generated, nothing executed

    model_sql(
        fake_ollama,
        "SELECT c.name, SUM(p.amount) AS revenue FROM sales.customers c "
        "JOIN sales.orders o ON o.customer_id = c.id JOIN sales.payments p ON p.order_id = o.id "
        "WHERE p.paid_at >= date_trunc('month', current_date) - interval '1 month' "
        "AND p.paid_at < date_trunc('month', current_date) "
        "GROUP BY c.id, c.name ORDER BY revenue DESC LIMIT 5",
    )
    second = ask(
        sql_client,
        cid,
        "Show me our best customers last month.",
        [{"term": "best customer", "option_id": "paid_revenue"}],
    )
    assert second["status"] == "executed", second["message"]
    assert second["columns"] == ["name", "revenue"]
    assert 1 <= second["row_count"] <= 5
    assert second["read_only"] is True
    assert second["definitions_used"][0]["term"] == "best customer"
    prompt = next(b for p, b in reversed(fake_ollama.requests) if p == "/api/chat")["messages"][1][
        "content"
    ]
    assert "Rank customers by net paid revenue" in prompt  # the chosen definition reaches the model
    assert "Today's date:" in prompt
    assert READER_PASSWORD not in prompt


def test_unsafe_model_sql_is_rejected_and_never_executed(
    sql_client: TestClient, fake_ollama: FakeOllama, demo_settings: Settings
) -> None:
    cid = demo_id(sql_client)
    for bad in [
        "DELETE FROM sales.payments",
        "SELECT 1; DROP TABLE sales.orders",
        "SELECT * FROM public.documents",
    ]:
        model_sql(fake_ollama, bad)
        out = ask(sql_client, cid, "How many payments are there?")
        assert out["status"] == "rejected", bad
        assert out["rows"] == []
        assert "rejected and not run" in out["message"]
    admin = create_engine(get_settings().database_url.set(database=demo_settings.demo_db_name))
    with admin.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM sales.payments")) > 0
        assert conn.scalar(text("SELECT to_regclass('sales.orders')")) is not None
    admin.dispose()


def test_slow_query_times_out_safely(sql_client: TestClient, fake_ollama: FakeOllama) -> None:
    cid = demo_id(sql_client)
    model_sql(
        fake_ollama,
        "SELECT count(*) FROM sales.order_items a, sales.order_items b, sales.order_items c",
    )
    out = ask(sql_client, cid, "Count every combination of order lines")
    assert out["status"] == "failed"
    assert "longer than 0.5 seconds" in out["message"]


def test_row_cap_and_model_clarification_and_unsupported(
    sql_client: TestClient, fake_ollama: FakeOllama
) -> None:
    cid = demo_id(sql_client)
    model_sql(fake_ollama, "SELECT id FROM sales.orders ORDER BY id")
    capped = ask(sql_client, cid, "List all order ids")
    assert capped["row_count"] == 50 and capped["truncated"] is True

    fake_ollama.chat_replies.append(
        json.dumps(
            {
                "status": "clarification_required",
                "explanation": "",
                "clarification": {
                    "question": "Which date should define 'recent'?",
                    "missing_concept": "recent",
                    "options": [
                        {"label": "Order date", "definition": "orders.order_date"},
                        {"label": "Payment date", "definition": "payments.paid_at"},
                    ],
                },
            }
        )
    )
    clar = ask(sql_client, cid, "Show recent big orders")
    assert clar["status"] == "clarification_required"
    assert clar["clarification"]["source"] == "model"
    assert clar["rows"] == []

    fake_ollama.chat_replies.append(
        json.dumps({"status": "unsupported", "explanation": "", "reason": "No employee data."})
    )
    unsup = ask(sql_client, cid, "What is the average employee salary?")
    assert unsup["status"] == "unsupported"
    assert unsup["message"] == "No employee data."


def test_superuser_or_writable_connection_is_refused(sql_client: TestClient) -> None:
    app = get_settings()
    r = sql_client.post(
        "/api/v1/sql/connections/test",
        json={
            "display_name": "App DB as owner",
            "host": app.postgres_host,
            "port": app.postgres_port,
            "database_name": "knowflow_demo_test",
            "username": app.postgres_user,
            "password": app.postgres_password.get_secret_value(),
            "allowed_schemas": ["sales"],
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "sql_role_not_read_only"
    bad_pw = sql_client.post(
        "/api/v1/sql/connections/test",
        json={
            "display_name": "x",
            "host": app.postgres_host,
            "port": app.postgres_port,
            "database_name": "knowflow_demo_test",
            "username": "knowflow_reader_test",
            "password": "wrong-password",
            "allowed_schemas": ["sales"],
        },
    )
    assert bad_pw.status_code == 422
    assert "wrong-password" not in bad_pw.text
    assert (
        sql_client.post(
            "/api/v1/sql/connections/test",
            json={
                "display_name": "x",
                "host": "h; rm",
                "port": 1,
                "database_name": "d",
                "username": "u",
                "password": "p",
                "allowed_schemas": ["pg_catalog"],
            },
        ).status_code
        == 422
    )


def test_user_connection_can_be_added_and_history_is_redacted(
    sql_client: TestClient, fake_ollama: FakeOllama, db_engine: Any
) -> None:
    app = get_settings()
    added = sql_client.post(
        "/api/v1/sql/connections/test",
        json={
            "display_name": "My read-only copy",
            "host": app.postgres_host,
            "port": app.postgres_port,
            "database_name": "knowflow_demo_test",
            "username": "knowflow_reader_test",
            "password": READER_PASSWORD,
            "allowed_schemas": ["sales"],
        },
    )
    assert added.status_code == 201, added.text
    assert READER_PASSWORD not in added.text
    cid = added.json()["id"]
    model_sql(
        fake_ollama,
        "SELECT count(*) AS n FROM sales.customers WHERE email = 'customer1@example.test'",
    )
    out = ask(sql_client, cid, "Is customer1@example.test a customer?")
    assert out["status"] == "executed"
    with db_engine.connect() as conn:
        stored = conn.scalar(
            text("SELECT sql_redacted FROM sql_queries ORDER BY created_at DESC LIMIT 1")
        )
        secret = conn.scalar(
            text("SELECT encrypted_secret_ref FROM sql_connections WHERE id = :i"), {"i": cid}
        )
    assert "customer1@example.test" not in stored and "'?'" in stored
    assert READER_PASSWORD not in secret
    history = sql_client.get(f"/api/v1/sql/connections/{cid}/history").json()
    assert history[0]["status"] == "executed"
    assert sql_client.delete(f"/api/v1/sql/connections/{cid}").status_code == 204
    assert sql_client.delete(f"/api/v1/sql/connections/{demo_id(sql_client)}").status_code == 409


def test_glossary_is_editable_and_validated(sql_client: TestClient) -> None:
    cid = demo_id(sql_client)
    current = sql_client.get(f"/api/v1/sql/schema/{cid}").json()["glossary"]
    bad = [
        *current,
        {
            "term": "loyal customer",
            "kind": "ambiguous",
            "options": [{"id": "a", "label": "A", "definition": "x"}],
        },
    ]
    assert sql_client.put(f"/api/v1/sql/connections/{cid}/glossary", json=bad).status_code == 422
    good = [g for g in current if g["term"] != "best customer"]
    saved = sql_client.put(f"/api/v1/sql/connections/{cid}/glossary", json=good).json()
    assert all(g["term"] != "best customer" for g in saved)


def test_failed_query_can_be_repaired_once(sql_client: TestClient, fake_ollama: FakeOllama) -> None:
    cid = demo_id(sql_client)
    model_sql(fake_ollama, "SELECT nmae FROM sales.customers")
    failed = ask(sql_client, cid, "List customer names")
    assert failed["status"] == "failed"
    assert failed["repairable"] is True
    assert "nmae" in failed["message"]

    model_sql(fake_ollama, "SELECT name FROM sales.customers ORDER BY name LIMIT 3")
    r = sql_client.post(
        "/api/v1/sql/query",
        json={
            "connection_id": cid,
            "question": "List customer names",
            "repair": {"sql": failed["sql"], "error": failed["message"]},
        },
    )
    fixed = r.json()
    assert fixed["status"] == "executed"
    assert fixed["row_count"] == 3
    prompt = next(b for p, b in reversed(fake_ollama.requests) if p == "/api/chat")["messages"][1][
        "content"
    ]
    assert "Your previous query failed" in prompt
    assert "nmae" in prompt

    # A repaired attempt that fails again is not offered for another repair.
    model_sql(fake_ollama, "SELECT still_wrong FROM sales.customers")
    again = sql_client.post(
        "/api/v1/sql/query",
        json={
            "connection_id": cid,
            "question": "List customer names",
            "repair": {"sql": "x", "error": "y"},
        },
    ).json()
    assert again["status"] == "failed"
    assert again["repairable"] is False
