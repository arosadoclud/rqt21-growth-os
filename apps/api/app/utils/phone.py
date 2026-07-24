from __future__ import annotations

import phonenumbers
from sqlalchemy import select
from sqlalchemy.orm import Session


class InvalidPhoneNumber(ValueError):
    """Distinct from 'not interpretable without a country' — the caller can
    use this distinction to give a clearer error message."""


def normalize_phone(value: str | None, default_country: str = "DO") -> str | None:
    """Return canonical E.164, or None for empty input.

    Raises InvalidPhoneNumber for a non-empty value that phonenumbers cannot
    parse as a possible+valid number, whether because of a malformed number or
    because it has no country code and default_country doesn't resolve it.
    """
    if value is None or not value.strip():
        return None
    try:
        parsed = phonenumbers.parse(value.strip(), default_country.upper())
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumber("invalid phone number") from exc
    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumber("invalid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def org_default_country(db: Session, organization_id) -> str:
    """Look up Organization.country_code; fall back to DO if row is missing."""
    from app.models.organization import Organization

    code = db.execute(
        select(Organization.country_code).where(Organization.id == organization_id)
    ).scalar_one_or_none()
    return code or "DO"
