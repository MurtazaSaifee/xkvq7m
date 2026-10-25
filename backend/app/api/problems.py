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
from app.core.security_headers import SECURITY_HEADERS

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


SNAPSHOT_UNAVAILABLE_DETAIL = "Data snapshot is not available"

# The OpenAPI entries for a problem response. Routes share them so the documented shape is one.
_PROBLEM_CONTENT: dict[str, Any] = {
    PROBLEM_MEDIA_TYPE: {"schema": ProblemDetail.model_json_schema()}
}
_INVALID_PARAMETERS_RESPONSE: dict[int | str, dict[str, Any]] = {
    422: {"description": "Invalid parameters", "content": _PROBLEM_CONTENT},
}
_SNAPSHOT_UNAVAILABLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    503: {"description": "The data snapshot is not available", "content": _PROBLEM_CONTENT},
}
_UNEXPECTED_ERROR_RESPONSE: dict[int | str, dict[str, Any]] = {
    500: {"description": "Unexpected server error", "content": _PROBLEM_CONTENT},
}
# For a route with query parameters that also needs the snapshot.
PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_INVALID_PARAMETERS_RESPONSE,
    **_SNAPSHOT_UNAVAILABLE_RESPONSE,
    **_UNEXPECTED_ERROR_RESPONSE,
}
# For a route that needs the snapshot but takes no parameters.
SNAPSHOT_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_SNAPSHOT_UNAVAILABLE_RESPONSE,
    **_UNEXPECTED_ERROR_RESPONSE,
}


def snapshot_unavailable() -> ProblemError:
    """The problem for a route that needs the data snapshot when there is none to read."""
    return ProblemError(
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.SERVICE_UNAVAILABLE.phrase,
        SNAPSHOT_UNAVAILABLE_DETAIL,
    )


def invalid_cutoff(error: ValueError) -> ProblemError:
    """The problem for a cutoff that is not a valid HH:MM time."""
    return ProblemError(
        HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid request", str(error), INVALID_PARAMETER
    )


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
    # This answer skips the middleware stack, so it carries the security headers itself.
    headers = dict(SECURITY_HEADERS)
    if request_id is not None:
        headers[REQUEST_ID_HEADER] = request_id
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
