"""Meta (Facebook Login / Instagram Graph) OAuth client — Phase 6A skeleton.

Fully implements the real OAuth Authorization Code flow against the actual
Graph API endpoints, but every method raises ``OAuthNotConfigured`` instead
of making a network call until ``META_APP_ID``, ``META_APP_SECRET`` and
``META_OAUTH_REDIRECT_URI`` are all set (Phase 6B — the user creates the
Meta App and pastes these in). Nothing about "preparing" this client
connects a real account; it only means the code path exists and is tested
against a mocked Graph API.

Scopes used for our use case: ``pages_show_list``, ``pages_manage_posts``,
``pages_read_engagement``, ``instagram_basic``, ``instagram_content_publish``
— never requested by this module directly; callers (Phase 6B connection UI)
pass the scope list explicitly so it's visible/auditable at the call site.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.oauth.base import (
    OAuthExchangeError,
    OAuthNotConfigured,
    OAuthTokenSet,
    expires_at_from_ttl,
)


class MetaOAuthClient:
    AUTHORIZE_HOST = "https://www.facebook.com"
    GRAPH_HOST = "https://graph.facebook.com"

    def __init__(
        self,
        *,
        app_id: str = "",
        app_secret: str = "",
        redirect_uri: str = "",
        api_version: str = "",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = app_id or settings.meta_app_id
        self._app_secret = app_secret or settings.meta_app_secret
        self._redirect_uri = redirect_uri or settings.meta_oauth_redirect_uri
        self._api_version = api_version or settings.meta_graph_api_version
        self._injected_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self._app_id and self._app_secret and self._redirect_uri)

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise OAuthNotConfigured(
                "META_APP_ID, META_APP_SECRET and META_OAUTH_REDIRECT_URI must all be "
                "set before the Meta OAuth flow can be used — see Phase 6B in the README."
            )

    def _client(self) -> httpx.AsyncClient:
        return self._injected_client or httpx.AsyncClient(timeout=15.0)

    def authorize_url(self, *, state: str, scopes: list[str]) -> str:
        self._require_configured()
        params = {
            "client_id": self._app_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
            "scope": ",".join(scopes),
            "response_type": "code",
        }
        return f"{self.AUTHORIZE_HOST}/{self._api_version}/dialog/oauth?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokenSet:
        """Authorization code -> short-lived user access token."""
        self._require_configured()
        params = {
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "redirect_uri": self._redirect_uri,
            "code": code,
        }
        url = f"{self.GRAPH_HOST}/{self._api_version}/oauth/access_token"
        async with self._client() as client:
            resp = await client.get(url, params=params)
        return self._parse_token_response(resp)

    async def exchange_long_lived_token(self, short_lived_token: str) -> OAuthTokenSet:
        """Short-lived (~1-2h) user token -> long-lived (~60 day) token.
        Meta has no classic refresh_token grant; this exchange is how
        connections stay alive without re-running the full OAuth dialog."""
        self._require_configured()
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._app_id,
            "client_secret": self._app_secret,
            "fb_exchange_token": short_lived_token,
        }
        url = f"{self.GRAPH_HOST}/{self._api_version}/oauth/access_token"
        async with self._client() as client:
            resp = await client.get(url, params=params)
        return self._parse_token_response(resp)

    async def debug_token(self, access_token: str) -> dict:
        """Inspect scopes/expiry/validity of a token via /debug_token —
        used by the connection "verify" action (Phase 6B) instead of
        guessing from local state."""
        self._require_configured()
        app_access_token = f"{self._app_id}|{self._app_secret}"
        params = {"input_token": access_token, "access_token": app_access_token}
        url = f"{self.GRAPH_HOST}/{self._api_version}/debug_token"
        async with self._client() as client:
            resp = await client.get(url, params=params)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            raise OAuthExchangeError(str(data.get("error", data))[:300])
        return data.get("data", data)

    def _parse_token_response(self, resp: httpx.Response) -> OAuthTokenSet:
        try:
            data = resp.json()
        except Exception as exc:
            raise OAuthExchangeError(f"non-JSON response from Meta ({resp.status_code})") from exc
        if resp.status_code >= 400 or "error" in data:
            message = data.get("error", {}).get("message", str(data))[:300]
            raise OAuthExchangeError(message)
        return OAuthTokenSet(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_at=expires_at_from_ttl(data.get("expires_in")),
            raw=data,
        )
