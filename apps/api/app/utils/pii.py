"""Server-side redaction of personally identifiable information.

Anything reachable by a role that must not see full PII (ANALYST, VIEWER) is
transformed here, on the server, BEFORE it is serialized into a response.
The frontend never receives the plaintext value and cannot leak it.
"""

from __future__ import annotations

from app.models.membership import Role

REDACTED_ROLES: frozenset[Role] = frozenset({Role.ANALYST, Role.VIEWER})


def role_can_see_full_pii(role: Role) -> bool:
    return role not in REDACTED_ROLES


def mask_email(value: str | None) -> str | None:
    if not value:
        return value
    at = value.find("@")
    if at < 1:
        return "***"
    local = value[:at]
    domain = value[at:]
    if len(local) <= 1:
        return f"{local}***{domain}"
    return f"{local[0]}***{domain}"


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = [c for c in value if c.isdigit()]
    if len(digits) <= 4:
        return "***"
    keep = "".join(digits[-4:])
    plus = "+" if value.startswith("+") else ""
    return f"{plus} ******{keep}"


def mask_notes(value: str | None) -> str | None:
    # Redacted roles never see freeform notes — sales/marketing may leave
    # sensitive context there.
    if not value:
        return None
    return None
