from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(
    *,
    user_id: str,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    issued = now or datetime.now(UTC)
    ttl = ttl_seconds if ttl_seconds is not None else settings.jwt_access_ttl_seconds
    expires = issued + timedelta(seconds=ttl)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "typ": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def generate_refresh_token() -> tuple[str, str]:
    """Return (plaintext, sha256_hex)."""
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
