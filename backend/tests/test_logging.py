import json
import logging

from app.core.logging import JsonFormatter, configure_logging
from app.core.request_context import bind_request_id


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formats_record_as_single_json_object():
    line = JsonFormatter().format(_record("cache miss", key="delivery-day", count=3))

    payload = json.loads(line)
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "cache miss"
    assert payload["key"] == "delivery-day"
    assert payload["count"] == 3
    assert payload["ts"].endswith("+00:00")


def test_uses_request_id_from_context_when_record_has_none():
    with bind_request_id("ctx-request-7"):
        payload = json.loads(JsonFormatter().format(_record("inside request")))

    assert payload["request_id"] == "ctx-request-7"


def test_request_id_is_null_outside_a_request():
    payload = json.loads(JsonFormatter().format(_record("startup")))

    assert payload["request_id"] is None


def test_uvicorn_access_log_is_silenced_in_favour_of_app_access_log():
    configure_logging()

    assert logging.getLogger("uvicorn.access").getEffectiveLevel() > logging.INFO
    assert logging.getLogger("uvicorn.error").getEffectiveLevel() <= logging.INFO
