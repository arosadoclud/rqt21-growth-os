from __future__ import annotations

import secrets

# base62 minus lookalikes (0, O, l, 1, I)
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"


def generate(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
