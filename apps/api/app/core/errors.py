"""Consistent error envelope with stable codes and request_id; never leaks stack traces (TRD §8)."""

import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    fields: list[dict[str, Any]] | None = None
    # Structured, user-safe context for clients (e.g. the existing document on a duplicate).
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """Raise for expected, user-explainable failures. `message` must be safe to show users."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def error_response(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id_var.get(), **extra)
    )
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(AppError, exc)  # Starlette routes only AppError here
    return error_response(exc.status_code, exc.code, exc.message, details=exc.details)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
    return error_response(exc.status_code, code, message)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    # Only location, message and type: input values may contain user data.
    fields = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return error_response(422, "validation_error", "The request is invalid.", fields=fields)


# SQLSTATE undefined_table / undefined_column: the code is newer than the database schema.
_SCHEMA_SQLSTATES = frozenset({"42P01", "42703"})


async def _database_error(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, DBAPIError) and getattr(exc.orig, "sqlstate", None) in _SCHEMA_SQLSTATES:
        logger.error("schema_not_migrated", extra={"error_type": type(exc).__name__})
        return error_response(
            503,
            "schema_not_migrated",
            "The database schema is out of date. Run: ./scripts/dev.ps1 migrate",
        )
    if isinstance(exc, OperationalError | PoolTimeoutError) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    ):
        logger.warning("database_unavailable", extra={"error_type": type(exc).__name__})
        return error_response(
            503,
            "database_unavailable",
            "The database is unavailable. Start it with: ./scripts/db.ps1 start",
        )
    return await _unhandled_error(_, exc)


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", extra={"error_type": type(exc).__name__})
    return error_response(500, "internal_error", "Something went wrong on the server.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(DBAPIError, _database_error)
    app.add_exception_handler(PoolTimeoutError, _database_error)
    app.add_exception_handler(Exception, _unhandled_error)
