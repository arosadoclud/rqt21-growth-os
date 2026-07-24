"""Double-submit-cookie CSRF protection.

Strategy: on login/refresh we set a non-HttpOnly cookie ``rqt_csrf`` containing a
random opaque token. Clients (our SPA) read the cookie and echo the value in the
``X-CSRF-Token`` header for every mutating request. Because SameSite=Lax already
blocks most cross-site POSTs, the header check is a defense-in-depth layer that
also guards against future SameSite=None cookies.

Exemptions:
- ``POST /api/v1/auth/login`` — no session yet, nothing to protect.
- ``POST /api/v1/auth/logout`` — idempotent revocation of the caller's own
  session. Even if forged, the worst outcome is signing the victim out.
- Requests without any auth cookie (``rqt_access`` / ``rqt_refresh``) — no
  authenticated session to hijack; validation would just confuse errors.
- Safe methods (GET, HEAD, OPTIONS).
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

CSRF_COOKIE = "rqt_csrf"
CSRF_HEADER = "x-csrf-token"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
EXEMPT_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        # Refresh only rotates tokens returned as HttpOnly cookies; a CSRF
        # attacker who can't read them gains nothing by triggering rotation.
        "/api/v1/auth/refresh",
    }
)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=settings.jwt_refresh_ttl_seconds,
        httponly=False,  # SPA must read it
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CSRF_COOKIE, domain=settings.cookie_domain or None, path="/"
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        if (
            method in SAFE_METHODS
            or not path.startswith("/api/v1/")
            or path in EXEMPT_PATHS
        ):
            return await call_next(request)

        # Only enforce for requests that carry an auth cookie. Public endpoints
        # (there are none mutating in v1, but future public webhooks may exist)
        # do their own signature check.
        has_auth_cookie = (
            request.cookies.get("rqt_access") is not None
            or request.cookies.get("rqt_refresh") is not None
        )
        if not has_auth_cookie:
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE)
        header_token = request.headers.get(CSRF_HEADER)

        if not cookie_token or not header_token:
            return JSONResponse(
                {"detail": "missing CSRF token"}, status_code=403
            )
        if not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(
                {"detail": "invalid CSRF token"}, status_code=403
            )
        return await call_next(request)
