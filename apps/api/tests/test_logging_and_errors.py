from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter
from app.monitoring.errors import (
    NullErrorReporter,
    SentryErrorReporter,
    get_error_reporter,
    reset_error_reporter,
)


def test_json_formatter_produces_valid_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="rqt21.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    out = formatter.format(record)
    data = json.loads(out)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "rqt21.test"


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="rqt21.test", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="failed", args=(), exc_info=None,
    )
    record.publication_id = "pub_123"
    data = json.loads(formatter.format(record))
    assert data["publication_id"] == "pub_123"


def test_null_reporter_does_not_raise():
    reporter = NullErrorReporter()
    reporter.capture_exception(ValueError("boom"), path="/x")
    reporter.capture_message("something happened", level="warning")


def test_get_error_reporter_defaults_to_null(monkeypatch):
    from app.core.config import settings

    reset_error_reporter()
    monkeypatch.setattr(settings, "error_reporter", "none")
    reporter = get_error_reporter()
    assert isinstance(reporter, NullErrorReporter)
    reset_error_reporter()


def test_get_error_reporter_uses_sentry_when_configured(monkeypatch):
    from app.core.config import settings

    reset_error_reporter()
    monkeypatch.setattr(settings, "error_reporter", "sentry")
    monkeypatch.setattr(settings, "sentry_dsn", "https://fake@sentry.example/1")
    reporter = get_error_reporter()
    assert isinstance(reporter, SentryErrorReporter)
    reset_error_reporter()


def test_get_error_reporter_falls_back_without_dsn(monkeypatch):
    from app.core.config import settings

    reset_error_reporter()
    monkeypatch.setattr(settings, "error_reporter", "sentry")
    monkeypatch.setattr(settings, "sentry_dsn", "")
    reporter = get_error_reporter()
    assert isinstance(reporter, NullErrorReporter)
    reset_error_reporter()
