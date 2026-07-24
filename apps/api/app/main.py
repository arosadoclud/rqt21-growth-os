from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.api.public_leads import router as public_leads_router
from app.api.redirect import router as redirect_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.csrf import CSRFMiddleware

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


def create_app() -> FastAPI:
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

    app.include_router(api_router)
    app.include_router(redirect_router)
    app.include_router(public_leads_router)
    return app


app = create_app()
