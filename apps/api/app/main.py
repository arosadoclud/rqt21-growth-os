from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.api.public_leads import router as public_leads_router
from app.api.redirect import router as redirect_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.csrf import CSRFMiddleware
from app.monitoring.errors import get_error_reporter

configure_logging()
logger = logging.getLogger("rqt21")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


def _validate_cors() -> list[str]:
    origins = settings.cors_origins_list
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS='*' is not allowed with credentials. "
            "List explicit origins."
        )
    return origins


def _validate_production() -> None:
    if not settings.is_production:
        return
    errors = settings.production_config_errors()
    if errors:
        raise RuntimeError(
            "Refusing to start in production with an insecure configuration:\n- "
            + "\n- ".join(errors)
        )


def create_app() -> FastAPI:
    _validate_production()
    app = FastAPI(title="RQT21 Growth OS API", version="0.1.0")

    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_validate_cors(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",
            "X-Organization-Id",
        ],
        expose_headers=["Retry-After"],
    )

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        get_error_reporter().capture_exception(
            exc, path=request.url.path, method=request.method
        )
        # Never leak internals (stack traces, exception messages) to the
        # client — same "sensitive errors stay server-side" rule that
        # already governs Generation Job errors and audit payloads.
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    app.include_router(api_router)
    app.include_router(redirect_router)
    app.include_router(public_leads_router)
    return app


app = create_app()
