"""IP anonymization.

Store an HMAC-SHA256 of the caller's IP address, not the address itself. The
HMAC key is the server's ``IP_HASH_SECRET`` (or falls back to ``JWT_SECRET``),
so hashes cannot be re-derived from public data. Truncated to 32 hex chars for
storage compactness — still 128 bits of surface.

What we store per click:
- ip_hash: this deterministic hash. Lets us count distinct visitors within a
  short window without retaining an identifier that traces back to a person.
- user_agent: raw string, truncated. Used for browser/OS breakdown.
- referrer: raw URL, truncated.

What we do NOT store:
- Plain IP address.
- Any browser fingerprint beyond user_agent.
- Third-party cookies.
"""

from __future__ import annotations

import hashlib
import hmac

from app.core.config import settings


def _key() -> bytes:
    key = getattr(settings, "ip_hash_secret", "") or settings.jwt_secret
    return key.encode("utf-8")


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    digest = hmac.new(_key(), ip.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:32]
