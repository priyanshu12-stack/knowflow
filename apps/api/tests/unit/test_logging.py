"""SEC-04 / SEC-08: JSON log lines carry request_id and redact secrets."""

import json
import logging

from app.core.logging import JsonFormatter, redact, request_id_var


def _format(**extra: object) -> dict[str, object]:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    for k, v in extra.items():
        setattr(record, k, v)
    return json.loads(JsonFormatter().format(record))  # type: ignore[no-any-return]


def test_line_is_json_with_request_id() -> None:
    token = request_id_var.set("req-12345678")
    try:
        line = _format(duration_ms=3.2)
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "hello"
    assert line["request_id"] == "req-12345678"
    assert line["duration_ms"] == 3.2


def test_sensitive_extras_are_redacted() -> None:
    line = _format(password="hunter2", db={"api_key": "k", "host": "localhost"})
    assert line["password"] == "[REDACTED]"
    assert line["db"] == {"api_key": "[REDACTED]", "host": "localhost"}


def test_redact_handles_nested_lists() -> None:
    assert redact([{"Authorization": "Bearer x"}, {"ok": 1}]) == [
        {"Authorization": "[REDACTED]"},
        {"ok": 1},
    ]
