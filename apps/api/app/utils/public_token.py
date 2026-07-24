"""High-entropy opaque tokens for public-facing identifiers that must not be
guessable or sequential (e.g. PublicLeadSource.public_token).

Unlike short_code (deliberately short & typeable for /r/{code} links), these
are long enough that brute-forcing them is infeasible, and they carry no
positional/sequential information.
"""

from __future__ import annotations

import secrets


def generate(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
