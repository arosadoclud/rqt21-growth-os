"""Generic OAuth2 abstraction (Phase 6A).

Deliberately provider-agnostic: an ``OAuthProvider`` builds an authorize
URL, exchanges an auth code for tokens, and (where the provider supports
it) refreshes/extends a token. Nothing here performs a network call at
import time or construction time — a provider client only ever calls out
when one of its async methods is invoked, and every implementation must
refuse (raise ``OAuthNotConfigured``) rather than silently no-op when its
required credentials are absent. See app.oauth.meta for the concrete Meta
implementation used by Phase 6B.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import settings


class OAuthError(Exception):
    pass


class OAuthNotConfigured(OAuthError):
    """Raised instead of making any network call when required app
    credentials (client id/secret/redirect URI) are missing. This is what
    keeps the framework safe to ship and exercise in Phase 6A without any
    real Meta App existing yet."""


class OAuthExchangeError(OAuthError):
    """The provider's token endpoint returned an error payload."""


@dataclass(frozen=True)
class OAuthTokenSet:
    access_token: str
    token_type: str
    expires_at: datetime | None
    refresh_token: str | None = None
    scope: str | None = None
    raw: dict | None = None


class OAuthProvider(Protocol):
    @property
    def is_configured(self) -> bool: ...

    def authorize_url(self, *, state: str, scopes: list[str]) -> str: ...

    async def exchange_code(self, code: str) -> OAuthTokenSet: ...


def _state_secret() -> str:
    return settings.credentials_encryption_key or settings.jwt_secret


def generate_state(*, purpose: str, ttl_seconds: int = 600) -> str:
    """Signed, expiring CSRF state value for the OAuth redirect round-trip.
    Format: ``<expires_at>.<purpose>.<signature>`` — nothing in it is
    guessable without the server secret, and it self-expires."""
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{expires_at}.{purpose}"
    sig = hmac.new(_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_state(state: str, *, purpose: str) -> bool:
    parts = state.split(".", 2)
    if len(parts) != 3:
        return False
    expires_at_str, state_purpose, sig = parts
    if state_purpose != purpose:
        return False
    try:
        expires_at = int(expires_at_str)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    payload = f"{expires_at_str}.{state_purpose}"
    expected = hmac.new(_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(expected, sig)


def expires_at_from_ttl(ttl_seconds: int | None) -> datetime | None:
    if ttl_seconds is None:
        return None
    from datetime import timedelta

    return datetime.now(UTC) + timedelta(seconds=ttl_seconds)
