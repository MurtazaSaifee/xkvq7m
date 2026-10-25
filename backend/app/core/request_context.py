"""Request ID propagation and per-request access logging, as a pure ASGI middleware."""

import logging
import re
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
access_logger = logging.getLogger("app.access")


def current_request_id() -> str | None:
    return _request_id.get()


@contextmanager
def bind_request_id(request_id: str) -> Generator[None]:
    """Attach ``request_id`` to every log record emitted inside the block."""
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def _incoming_request_id(scope: Scope) -> str | None:
    candidate = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if candidate and _SAFE_REQUEST_ID.match(candidate):
        return candidate
    return None


class RequestContextMiddleware:
    """Assigns a request ID, echoes it in the response, and logs one access line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        token = _request_id.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (REQUEST_ID_HEADER.encode(), request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            access_logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            _request_id.reset(token)
