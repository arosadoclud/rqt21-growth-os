"""Error reporting abstraction (Phase 6A).

``ErrorReporter`` is the seam between "something went wrong" call sites
(the global exception handler, worker task failures) and wherever that
should actually be surfaced. ``NullErrorReporter`` is the default — it
just logs, matching every prior phase's behavior exactly. ``SentryReporter``
only activates when ``ERROR_REPORTER=sentry`` AND ``SENTRY_DSN`` is set;
sentry_sdk is initialized lazily on first use, never at import time, so a
process with no DSN configured never even imports sentry_sdk's init path.

Never pass raw request bodies, PII, or secrets into ``context`` — same rule
as app.audit.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("rqt21.errors")


class ErrorReporter(Protocol):
    def capture_exception(self, exc: BaseException, **context: object) -> None: ...

    def capture_message(self, message: str, *, level: str = "error", **context: object) -> None: ...


class NullErrorReporter:
    """Logs only — the default and what every environment used through
    Phase 5 got implicitly."""

    def capture_exception(self, exc: BaseException, **context: object) -> None:
        logger.error("unhandled exception: %s", exc, exc_info=exc, extra=context)

    def capture_message(self, message: str, *, level: str = "error", **context: object) -> None:
        getattr(logger, level, logger.error)(message, extra=context)


class SentryErrorReporter:
    """Thin wrapper around sentry_sdk. Initialized once, lazily, on first
    use — constructing this class does not itself talk to Sentry."""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.0)
        self._initialized = True

    def capture_exception(self, exc: BaseException, **context: object) -> None:
        self._ensure_init()
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
        logger.error("unhandled exception (reported to sentry): %s", exc)

    def capture_message(self, message: str, *, level: str = "error", **context: object) -> None:
        self._ensure_init()
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)


_reporter: ErrorReporter | None = None


def get_error_reporter() -> ErrorReporter:
    global _reporter
    if _reporter is not None:
        return _reporter
    if settings.error_reporter == "sentry" and settings.sentry_dsn:
        _reporter = SentryErrorReporter()
    else:
        _reporter = NullErrorReporter()
    return _reporter


def reset_error_reporter() -> None:
    """Test hook — forces re-evaluation of settings on next get()."""
    global _reporter
    _reporter = None
