"""Stdlib JSON logging. One JSON object per line on stdout, tagged with the request ID."""

import datetime as dt
import json
import logging
import sys
from typing import Any

from app.core.request_context import current_request_id

# Attributes every LogRecord has. Anything else was passed via `extra=` and is emitted as-is.
_STANDARD_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or current_request_id(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_ATTRS and key != "request_id":
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _JsonStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker class so configure_logging can replace only the handler it installed."""


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing, _JsonStreamHandler):
            root.removeHandler(existing)
    handler = _JsonStreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Route uvicorn's own loggers through the root JSON handler instead of their plain-text ones.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
