"""RFC 7807 problem responses, shared by every API route.

Raise ``ProblemError`` from any route for a specific problem. HTTP errors (including unknown
routes), request validation errors and unexpected exceptions are rendered in the same shape, so
every error under ``/api`` is ``application/problem+json``. An unexpected exception is logged with
its request ID and answered with a generic 500, so no stack trace reaches the client.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import REQUEST_ID_HEADER

PROBLEM_MEDIA_TYPE = "application/problem+json"
ABOUT_BLANK = "about:blank"
INVALID_PARAMETER = "urn:wind-forecast:problem:invalid-parameter"
UNEXPECTED_ERROR_DETAIL = "An unexpected error occurred. The server has logged it."

error_logger = logging.getLogger("app.errors")


class ProblemError(Exception):
    """An error a route raises to answer with a problem document."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        problem_type: str = ABOUT_BLANK,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.problem_type = problem_type


class ProblemDetail(BaseModel):
    """The body of an error response. ``errors`` lists each invalid parameter, if any."""

    type: str = ABOUT_BLANK
    title: str
    status: int
    detail: str
    instance: str
    errors: list[dict[str, Any]] | None = None


def _problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
    problem_type: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": problem_type,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=headers
    )


async def _handle_problem(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ProblemError)
    return _problem_response(request, error.status, error.title, error.detail, error.problem_type)


async def _handle_http_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    title = HTTPStatus(error.status_code).phrase
    return _problem_response(request, error.status_code, title, str(error.detail), ABOUT_BLANK)


async def _handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    errors = [
        {"loc": [str(part) for part in item["loc"]], "msg": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    detail = "; ".join(f"{'.'.join(item['loc'])}: {item['msg']}" for item in errors)
    return _problem_response(
        request,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "Invalid request",
        detail,
        INVALID_PARAMETER,
        errors=errors,
    )


async def _handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """Log the exception with its request ID, and answer 500 without the details of the failure."""
    request_id: str | None = getattr(request.state, "request_id", None)
    error_logger.error(
        "unexpected error",
        exc_info=error,
        extra={"request_id": request_id, "path": request.url.path},
    )
    headers = None if request_id is None else {REQUEST_ID_HEADER: request_id}
    return _problem_response(
        request,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
        UNEXPECTED_ERROR_DETAIL,
        ABOUT_BLANK,
        headers=headers,
    )


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemError, _handle_problem)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    # Starlette's catch-all runs outside the middleware and re-raises after responding, so the
    # server still logs the traceback in its own log.
    app.add_exception_handler(Exception, _handle_unexpected_error)
