"""Human-facing short identifiers.

Every domain row keeps a UUID primary key. `public_id` is a stable, short,
prefix-tagged string for URLs, logs and UI. Format: ``{prefix}_{8 base32 chars}``.
Collisions per prefix are ~1 in 10^12; callers retry on conflict.
"""

from __future__ import annotations

import secrets

_ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"  # ambiguous chars removed


def _random(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def make(prefix: str, length: int = 8) -> str:
    return f"{prefix}_{_random(length)}"
