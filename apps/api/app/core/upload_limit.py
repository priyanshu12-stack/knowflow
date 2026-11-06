"""Reject oversized uploads before the body is read (SEC-01, SEC-07).

Starlette parses multipart bodies (spooling files to disk) before an endpoint runs, so the size
limit has to be enforced here, from `Content-Length`. The storage layer re-checks the real byte
count while streaming. Requests without a length are refused rather than read without a bound.
"""

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

# Multipart boundaries and part headers on top of the file itself.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class UploadSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, path: str, max_file_bytes: int) -> None:
        self.app = app
        self.path = path.rstrip("/")
        self.max_file_bytes = max_file_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != self.path
        ):
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length is None or not length.isdigit():
            response = error_response(
                411, "length_required", "Uploads must include a Content-Length header."
            )
        elif int(length) > self.max_file_bytes + MULTIPART_OVERHEAD_BYTES:
            limit_mb = self.max_file_bytes // (1024 * 1024)
            response = error_response(
                413, "file_too_large", f"The file is larger than the {limit_mb} MB limit."
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)
