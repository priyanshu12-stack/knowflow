"""TRD §11 "Secrets exposure" / "Sensitive logging": credentials never reach the log."""

import io
import json
import logging

from app.core.logging import JsonFormatter, redact, redact_text


def test_credentials_inside_text_are_redacted() -> None:
    assert redact_text("postgresql+psycopg://knowflow_reader:S3cr3t-pw@localhost:5432/db") == (
        "postgresql+psycopg://knowflow_reader:[REDACTED]@localhost:5432/db"
    )
    assert redact_text("PGPASSWORD=hunter2 psql") == "PGPASSWORD=[REDACTED] psql"
    assert redact_text('password: "abc"') == 'password: "[REDACTED]"'
    assert redact_text("Authorization: Bearer eyJabc.def") == "Authorization: Bearer [REDACTED]"
    assert "gAAAAAB" not in redact_text("stored gAAAAABnXyZ1234567890abcdefghijk_-==")
    plain = "the word password appears but no value follows"
    assert redact_text(plain) == plain


def test_structured_extras_are_redacted_by_key_and_value() -> None:
    out = redact({"db_password": "x", "nested": {"dsn": "postgres://u:p@h/d"}, "count": 3})
    assert out == {
        "db_password": "[REDACTED]",
        "nested": {"dsn": "postgres://u:[REDACTED]@h/d"},
        "count": 3,
    }


def test_formatter_redacts_message_extras_and_tracebacks() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("redaction-test")
    log.handlers[:] = [handler]
    log.propagate = False
    try:
        raise RuntimeError("connect failed for postgres://admin:topsecret@db/app")
    except RuntimeError:
        log.exception("login with password=topsecret failed", extra={"api_key": "k-123"})
    line = json.loads(stream.getvalue())
    assert "topsecret" not in json.dumps(line)
    assert line["api_key"] == "[REDACTED]"
