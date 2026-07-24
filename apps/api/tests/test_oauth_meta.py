from __future__ import annotations

import asyncio

import httpx
import pytest

from app.oauth.base import (
    OAuthExchangeError,
    OAuthNotConfigured,
    generate_state,
    verify_state,
)
from app.oauth.meta import MetaOAuthClient


def _configured_client(handler) -> MetaOAuthClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return MetaOAuthClient(
        app_id="test-app-id",
        app_secret="test-app-secret",
        redirect_uri="https://app.example.com/oauth/meta/callback",
        api_version="v21.0",
        http_client=http_client,
    )


def test_unconfigured_client_refuses_authorize_url():
    client = MetaOAuthClient(app_id="", app_secret="", redirect_uri="")
    assert client.is_configured is False
    with pytest.raises(OAuthNotConfigured):
        client.authorize_url(state="s", scopes=["pages_show_list"])


def test_unconfigured_client_refuses_exchange():
    client = MetaOAuthClient(app_id="", app_secret="", redirect_uri="")
    with pytest.raises(OAuthNotConfigured):
        asyncio.run(client.exchange_code("some-code"))


def test_authorize_url_contains_expected_params():
    client = _configured_client(lambda req: httpx.Response(200, json={}))
    url = client.authorize_url(state="abc123", scopes=["pages_show_list", "instagram_basic"])
    assert url.startswith("https://www.facebook.com/v21.0/dialog/oauth?")
    assert "client_id=test-app-id" in url
    assert "state=abc123" in url
    assert "pages_show_list" in url


def test_exchange_code_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "oauth/access_token" in str(request.url)
        return httpx.Response(
            200, json={"access_token": "short-lived-token", "token_type": "bearer", "expires_in": 5183944}
        )

    client = _configured_client(handler)
    result = asyncio.run(client.exchange_code("auth-code-123"))
    assert result.access_token == "short-lived-token"
    assert result.expires_at is not None


def test_exchange_code_provider_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Invalid verification code format."}})

    client = _configured_client(handler)
    with pytest.raises(OAuthExchangeError):
        asyncio.run(client.exchange_code("bad-code"))


def test_exchange_long_lived_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "fb_exchange_token" in str(request.url)
        return httpx.Response(
            200, json={"access_token": "long-lived-token", "token_type": "bearer", "expires_in": 5183944}
        )

    client = _configured_client(handler)
    result = asyncio.run(client.exchange_long_lived_token("short-lived-token"))
    assert result.access_token == "long-lived-token"


def test_debug_token_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"is_valid": True, "scopes": ["pages_show_list"]}})

    client = _configured_client(handler)
    data = asyncio.run(client.debug_token("some-token"))
    assert data["is_valid"] is True


def test_debug_token_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Invalid OAuth access token."}})

    client = _configured_client(handler)
    with pytest.raises(OAuthExchangeError):
        asyncio.run(client.debug_token("bad-token"))


def test_state_roundtrip():
    state = generate_state(purpose="meta-connect")
    assert verify_state(state, purpose="meta-connect") is True
    assert verify_state(state, purpose="other-purpose") is False


def test_state_rejects_tampered_signature():
    state = generate_state(purpose="meta-connect")
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
    assert verify_state(tampered, purpose="meta-connect") is False


def test_state_rejects_expired():
    state = generate_state(purpose="meta-connect", ttl_seconds=-1)
    assert verify_state(state, purpose="meta-connect") is False


def test_state_rejects_malformed():
    assert verify_state("not-a-valid-state", purpose="meta-connect") is False
    assert verify_state("", purpose="meta-connect") is False
