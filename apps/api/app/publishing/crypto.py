"""Symmetric encryption for PublishingConnection credentials at rest.

Credentials are encrypted before they ever touch the database and decrypted
only in-process when a provider adapter needs them to make a real call
(never in this MVP, since only MOCK/MANUAL are live). The API never returns
the encrypted blob or the plaintext to the client — see
app.schemas.publishing.PublishingConnectionRead, which has no credentials
field at all.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    secret = settings.credentials_encryption_key or settings.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_credentials(data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def decrypt_credentials(token: str) -> dict[str, Any]:
    payload = _fernet().decrypt(token.encode("utf-8"))
    return json.loads(payload.decode("utf-8"))


def last_four(data: dict[str, Any]) -> str | None:
    """Best-effort: surface only the last 4 chars of a token-like value for
    display, never the full secret."""
    for key in ("access_token", "token", "api_key", "secret"):
        val = data.get(key)
        if isinstance(val, str) and len(val) >= 4:
            return val[-4:]
    return None
