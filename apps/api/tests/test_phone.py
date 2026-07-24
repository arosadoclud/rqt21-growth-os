from __future__ import annotations

import pytest

from app.models.membership import Role
from app.utils.phone import InvalidPhoneNumber, normalize_phone


def test_normalize_local_do_number():
    # Dominican Republic local format, no country code -> resolved via default.
    assert normalize_phone("8092223333", "DO") == "+18092223333"


def test_normalize_international_number_ignores_default():
    # Already has a country code; default_country must not override it.
    assert normalize_phone("+34611222333", "DO") == "+34611222333"


def test_normalize_invalid_number_raises():
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("123", "DO")


def test_normalize_empty_returns_none():
    assert normalize_phone(None, "DO") is None
    assert normalize_phone("   ", "DO") is None


def test_lead_endpoint_rejects_invalid_phone(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "phone-bad@example.com")
    r = client.post("/api/v1/leads", json={"first_name": "X", "phone": "123"})
    assert r.status_code == 422


def test_lead_endpoint_normalizes_local_do_number(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "phone-do@example.com")
    r = client.post(
        "/api/v1/leads", json={"first_name": "X", "phone": "809 222 3333"}
    )
    assert r.status_code == 201
    assert r.json()["phone"] == "+18092223333"


def test_lead_whatsapp_normalized_too(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "phone-wa@example.com")
    r = client.post(
        "/api/v1/leads", json={"first_name": "X", "whatsapp": "809-222-3333"}
    )
    assert r.status_code == 201
    assert r.json()["whatsapp"] == "+18092223333"


def test_update_lead_renormalizes_phone(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "phone-upd@example.com")
    lead = client.post(
        "/api/v1/leads", json={"first_name": "X", "email": "x@example.com"}
    ).json()
    r = client.patch(f"/api/v1/leads/{lead['id']}", json={"phone": "809 222 3333"})
    assert r.status_code == 200
    assert r.json()["phone"] == "+18092223333"


def test_update_lead_rejects_invalid_phone(bootstrap):
    client, _, _ = bootstrap(Role.OWNER, "phone-upd-bad@example.com")
    lead = client.post(
        "/api/v1/leads", json={"first_name": "X", "email": "x2@example.com"}
    ).json()
    r = client.patch(f"/api/v1/leads/{lead['id']}", json={"phone": "1"})
    assert r.status_code == 422
