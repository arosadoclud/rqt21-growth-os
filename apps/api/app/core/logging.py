"""Structured logging setup (Phase 6A).

``LOG_FORMAT=json`` emits one JSON object per line — what every log
aggregator (CloudWatch, Loki, Datadog, etc.) expects. ``LOG_FORMAT=text``
(default, dev-friendly) keeps the stdlib's normal formatter. Never logs PII
or secrets — same rule that already applies to app.audit; this module only
touches *how* log lines are shaped, not what callers choose to log.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings

_RESERVED = frozenset(logging.LogRecord(
    "", 0, "", 0, "", (), None
).__dict__.keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )

    root.handlers = [handler]
