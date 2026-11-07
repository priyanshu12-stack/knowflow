"""Structured JSON logging with request correlation and secret redaction (TRD §3, §11)."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_KEY = re.compile(r"pass(word)?|secret|token|authorization|api[_-]?key|cookie", re.I)
_REDACTED = "[REDACTED]"

# Attributes present on every LogRecord; anything else was passed via `extra=`.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys() | {"message", "asctime"}
)


# Secrets that can appear inside free text (driver errors, exception messages).
_TEXT_PATTERNS = (
    # scheme://user:password@host  ->  scheme://user:[REDACTED]@host
    (
        re.compile(r"\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+(@)", re.I),
        r"\g<1>" + _REDACTED + r"\g<2>",
    ),
    # password=..., password: "...", PGPASSWORD=...
    (
        re.compile(
            r"((?:pg)?pass(?:word)?|secret|api[_-]?key|token)(\s*[=:]\s*)(['\"]?)[^\s'\",;]+",
            re.I,
        ),
        r"\g<1>\g<2>\g<3>" + _REDACTED,
    ),
    # Fernet tokens (encrypted connection secrets)
    (re.compile(r"gAAAAA[A-Za-z0-9_\-=]{20,}"), _REDACTED),
    # Authorization: Bearer xxx
    (re.compile(r"(bearer\s+)[A-Za-z0-9._\-]+", re.I), r"\g<1>" + _REDACTED),
)


def redact_text(text: str) -> str:
    for pattern, replacement in _TEXT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value: Any) -> Any:
    """Recursively replace values whose key looks sensitive, and secrets inside strings."""
    if isinstance(value, dict):
        return {
            k: _REDACTED if _SENSITIVE_KEY.search(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        extras = {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}
        payload.update(redact(extras))
        if record.exc_info:
            # Stack traces go to the local log only, never to API responses.
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Uvicorn's access log duplicates our request log line.
    logging.getLogger("uvicorn.access").disabled = True
    # httpx logs every outbound call at INFO; our own logs record what matters.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
