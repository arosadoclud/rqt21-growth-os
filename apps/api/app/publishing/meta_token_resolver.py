"""Meta Page Access Token resolution — the Kingdom Studio pattern.

Storing a single, static Page Access Token on a PublishingConnection has a
problem: Meta can invalidate it (password change, permission review, token
rotation) with no warning, and the only fix is a human re-pasting a fresh
token from Graph API Explorer every time.

Kingdom Studio (github.com/arosadoclud/kingdom-studio, a separate project of
the same user, already in production) avoids this by never storing a page
token at all. It stores one long-lived *base* token — a Business Manager
System User token, which Meta does not expire — and resolves the
page-specific token fresh, on every single publish/verify call, via:

    GET /{page_id}?fields=access_token&access_token=<base_token>

This module ports that same mechanism into RQT21. A META
PublishingConnection may store `credentials.base_access_token` instead of
(or in addition to) a static `credentials.access_token`; when a base token
is present it always wins, and the page token used for that call is never
more than a few seconds old.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.publishing.adapters import PublishPermanentError, PublishRecoverableError
from app.publishing.crypto import decrypt_credentials

if TYPE_CHECKING:
    from app.models.publishing import PublishingConnection

GRAPH_HOST = "https://graph.facebook.com"


class MetaTokenResolutionError(PublishPermanentError):
    pass


async def resolve_page_access_token(
    base_token: str,
    page_id: str,
    *,
    api_version: str = "",
    http_client: object | None = None,
) -> str:
    """Exchange a long-lived base token for the current access token of one
    specific Facebook Page / Instagram-linked page, via the Graph API."""
    if not base_token or not page_id:
        raise MetaTokenResolutionError(
            "a base_access_token and a page/account id are both required to "
            "resolve a fresh page access token"
        )
    import httpx as httpx_lib

    version = api_version or settings.meta_graph_api_version
    client = http_client or httpx_lib.AsyncClient(timeout=15.0)
    try:
        resp = await client.get(
            f"{GRAPH_HOST}/{version}/{page_id}",
            params={"fields": "access_token", "access_token": base_token},
        )
    except httpx_lib.HTTPError as exc:
        raise PublishRecoverableError(
            f"network error resolving Meta page token: {exc}"
        ) from exc
    finally:
        if http_client is None:
            await client.aclose()

    try:
        data = resp.json()
    except Exception as exc:
        raise MetaTokenResolutionError(
            f"non-JSON Graph API response resolving page token ({resp.status_code})"
        ) from exc

    error = data.get("error")
    if error:
        raise MetaTokenResolutionError(
            "Graph API rejected the base token while resolving the page "
            f"token: {error.get('message', error)}"
        )
    token = data.get("access_token")
    if not token:
        raise MetaTokenResolutionError(
            "Graph API response did not include a page access_token — is "
            "the base token missing pages_show_list / Business Manager access?"
        )
    return token


async def verify_meta_account_reachable(
    access_token: str,
    external_account_id: str,
    *,
    api_version: str = "",
    http_client: object | None = None,
) -> None:
    """A real connectivity check for the "verify connection" flow: does this
    access token actually see this Facebook Page / Instagram Business
    Account? Raises on any failure; returns None on success.

    This exists because MetaPublishingProvider.validate() is a pure local
    field-presence check (no network call) that, for INSTAGRAM, always
    requires a publication-ready asset URL — appropriate when validating a
    real draft, but wrong for a bare "is this connection alive" ping, which
    has no asset yet and shouldn't need one."""
    if not access_token or not external_account_id:
        raise MetaTokenResolutionError(
            "missing access token or external account id to verify"
        )
    import httpx as httpx_lib

    version = api_version or settings.meta_graph_api_version
    client = http_client or httpx_lib.AsyncClient(timeout=15.0)
    try:
        resp = await client.get(
            f"{GRAPH_HOST}/{version}/{external_account_id}",
            params={"fields": "id", "access_token": access_token},
        )
    except httpx_lib.HTTPError as exc:
        raise PublishRecoverableError(
            f"network error verifying Meta account: {exc}"
        ) from exc
    finally:
        if http_client is None:
            await client.aclose()

    try:
        data = resp.json()
    except Exception as exc:
        raise MetaTokenResolutionError(
            f"non-JSON Graph API response verifying account ({resp.status_code})"
        ) from exc

    error = data.get("error")
    if error:
        raise MetaTokenResolutionError(
            f"Graph API rejected access while verifying the account: {error.get('message', error)}"
        )


async def resolve_connection_access_token(connection: PublishingConnection) -> str:
    """The token to hand to MetaPublishingProvider for this connection.

    Prefers `credentials.base_access_token` (resolved fresh every call, per
    module docstring). Falls back to a static `credentials.access_token` for
    connections that predate this mechanism. Any failure — missing
    credentials, undecryptable blob, base token rejected by Graph — collapses
    to "" so the caller's existing "not configured" handling applies.

    The Graph API only resolves tokens against a Facebook Page id
    (`GET /{page_id}?fields=access_token`) — there is no equivalent
    endpoint for an Instagram Business Account id directly. So for a
    platform=INSTAGRAM connection, `external_account_id` holds the IG
    account id (the actual publish target), which is *not* what the token
    should be resolved against; `credentials.page_id` must carry the
    linked Facebook Page id instead. For platform=FACEBOOK connections the
    two are the same, so `page_id` can be omitted and `external_account_id`
    is used directly."""
    if not connection.credentials_encrypted:
        return ""
    try:
        creds = decrypt_credentials(connection.credentials_encrypted)
    except Exception:
        return ""

    base_token = creds.get("base_access_token", "")
    if base_token:
        page_id = creds.get("page_id") or connection.external_account_id or ""
        try:
            return await resolve_page_access_token(base_token, page_id)
        except Exception:
            return ""
    return creds.get("access_token", "")
