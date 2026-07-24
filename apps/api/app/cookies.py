from __future__ import annotations

from fastapi import Response

from app.core.config import settings
from app.csrf import CSRF_COOKIE
from app.deps import ACCESS_COOKIE, REFRESH_COOKIE


def _samesite() -> str:
    return settings.cookie_samesite


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        max_age=settings.jwt_access_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=_samesite(),
        domain=settings.cookie_domain or None,
        path="/",
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.jwt_refresh_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=_samesite(),
        domain=settings.cookie_domain or None,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            key=name,
            domain=settings.cookie_domain or None,
            path="/",
        )
