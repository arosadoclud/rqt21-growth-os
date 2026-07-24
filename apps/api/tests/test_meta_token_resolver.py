"""Regression tests for the Kingdom Studio base-token pattern: a META
connection storing `credentials.base_access_token` must resolve a fresh
page access token from the Graph API on every call, instead of relying on
a static, possibly-stale `credentials.access_token`. See
app.publishing.meta_token_resolver.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.publishing.adapters import PublishPermanentError
from app.publishing.crypto import encrypt_credentials
from app.publishing.meta_token_resolver import (
    resolve_connection_access_token,
    resolve_page_access_token,
)


class _FakeConnection:
    def __init__(self, credentials_encrypted: str | None, external_account_id: str = "") -> None:
        self.credentials_encrypted = credentials_encrypted
        self.external_account_id = external_account_id


def test_resolve_page_access_token_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/1228107327050361"
        assert request.url.params["access_token"] == "base-token-abc"
        assert request.url.params["fields"] == "access_token"
        return httpx.Response(
            200, json={"access_token": "fresh-page-token-xyz", "id": "1228107327050361"}
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with client:
            return await resolve_page_access_token(
                "base-token-abc", "1228107327050361", api_version="v21.0", http_client=client
            )

    assert asyncio.run(run()) == "fresh-page-token-xyz"


def test_resolve_page_access_token_graph_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "Invalid OAuth access token", "code": 190}}
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with client:
            await resolve_page_access_token(
                "expired-base-token", "123", api_version="v21.0", http_client=client
            )

    with pytest.raises(PublishPermanentError):
        asyncio.run(run())


def test_resolve_page_access_token_missing_args():
    with pytest.raises(PublishPermanentError):
        asyncio.run(resolve_page_access_token("", "123"))
    with pytest.raises(PublishPermanentError):
        asyncio.run(resolve_page_access_token("base-token", ""))


def test_resolve_connection_access_token_prefers_base_token(monkeypatch):
    conn = _FakeConnection(
        encrypt_credentials({"base_access_token": "base-tok", "access_token": "stale-page-tok"}),
        external_account_id="page-1",
    )

    async def fake_resolve(base_token, page_id, **kwargs):
        assert base_token == "base-tok"
        assert page_id == "page-1"
        return "freshly-resolved-token"

    monkeypatch.setattr(
        "app.publishing.meta_token_resolver.resolve_page_access_token", fake_resolve
    )
    token = asyncio.run(resolve_connection_access_token(conn))
    assert token == "freshly-resolved-token"


def test_resolve_connection_access_token_falls_back_to_static_token():
    conn = _FakeConnection(
        encrypt_credentials({"access_token": "static-page-tok"}), external_account_id="page-1"
    )
    token = asyncio.run(resolve_connection_access_token(conn))
    assert token == "static-page-tok"


def test_resolve_connection_access_token_no_credentials():
    conn = _FakeConnection(None)
    assert asyncio.run(resolve_connection_access_token(conn)) == ""


def test_resolve_connection_access_token_base_token_failure_swallowed(monkeypatch):
    conn = _FakeConnection(
        encrypt_credentials({"base_access_token": "revoked-base-tok"}),
        external_account_id="page-1",
    )

    async def fake_resolve(base_token, page_id, **kwargs):
        raise PublishPermanentError("base token rejected")

    monkeypatch.setattr(
        "app.publishing.meta_token_resolver.resolve_page_access_token", fake_resolve
    )
    assert asyncio.run(resolve_connection_access_token(conn)) == ""
