from __future__ import annotations

import asyncio

import httpx
import pytest

from app.publishing.adapters import (
    MetaPublishingProvider,
    PublicationPayload,
    PublishPermanentError,
    PublishRateLimited,
    PublishRecoverableError,
)


def _payload(**overrides) -> PublicationPayload:
    base = dict(
        publication_id="pub-1",
        platform="FACEBOOK",
        publication_type="POST",
        caption="Hola mundo",
        title=None,
        cta=None,
        connection_external_account_id="page-123",
        asset_public_url=None,
    )
    base.update(overrides)
    return PublicationPayload(**base)


def _provider(handler, *, enabled=True, token="page-access-token", monkeypatch=None):
    if monkeypatch is not None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "meta_publishing_enabled", enabled)
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return MetaPublishingProvider(token, http_client=http_client, api_version="v21.0")


def test_not_ready_without_enabled_flag(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "meta_publishing_enabled", False)
    provider = MetaPublishingProvider("some-token")
    with pytest.raises(PublishPermanentError):
        asyncio.run(provider.publish(_payload(), "idem-1"))


def test_not_ready_without_token(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "meta_publishing_enabled", True)
    provider = MetaPublishingProvider("")
    with pytest.raises(PublishPermanentError):
        asyncio.run(provider.publish(_payload(), "idem-1"))


def test_validate_reports_missing_account_id(monkeypatch):
    provider = _provider(lambda r: httpx.Response(200, json={}), monkeypatch=monkeypatch)
    result = asyncio.run(
        provider.validate(_payload(connection_external_account_id=None))
    )
    assert result.ok is False
    assert any("account id" in e for e in result.errors)


def test_validate_instagram_requires_public_url(monkeypatch):
    provider = _provider(lambda r: httpx.Response(200, json={}), monkeypatch=monkeypatch)
    result = asyncio.run(
        provider.validate(_payload(platform="INSTAGRAM", asset_public_url=None))
    )
    assert result.ok is False
    assert any("publicly reachable" in e for e in result.errors)


def test_publish_facebook_photo_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/page-123/photos" in str(request.url)
        return httpx.Response(200, json={"post_id": "page-123_555", "id": "555"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    result = asyncio.run(
        provider.publish(_payload(asset_public_url="https://cdn.example.com/x.jpg"), "idem-1")
    )
    assert result.external_publication_id == "page-123_555"
    assert "facebook.com" in result.external_url


def test_publish_facebook_video_uses_videos_endpoint_with_thumb(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "/page-123/videos" in url
        assert "file_url=" in url
        assert "thumb=" in url
        return httpx.Response(200, json={"post_id": "page-123_777", "id": "777"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    result = asyncio.run(
        provider.publish(
            _payload(
                publication_type="REEL",
                asset_public_url="https://cdn.example.com/reel.mp4",
                thumbnail_public_url="https://cdn.example.com/cover.png",
            ),
            "idem-1",
        )
    )
    assert result.external_publication_id == "page-123_777"


def test_publish_facebook_video_without_thumb_omits_param(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "/page-123/videos" in url
        assert "thumb=" not in url
        return httpx.Response(200, json={"post_id": "page-123_778", "id": "778"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    asyncio.run(
        provider.publish(
            _payload(publication_type="REEL", asset_public_url="https://cdn.example.com/reel.mp4"),
            "idem-1",
        )
    )


def test_publish_facebook_text_post_when_no_asset(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/page-123/feed" in str(request.url)
        return httpx.Response(200, json={"id": "999"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    result = asyncio.run(provider.publish(_payload(asset_public_url=None), "idem-1"))
    assert result.external_publication_id == "999"


def test_publish_instagram_two_step_flow(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/media_publish" in str(request.url):
            return httpx.Response(200, json={"id": "ig-media-1"})
        return httpx.Response(200, json={"id": "creation-container-1"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    result = asyncio.run(
        provider.publish(
            _payload(
                platform="INSTAGRAM",
                connection_external_account_id="ig-user-1",
                asset_public_url="https://cdn.example.com/x.jpg",
            ),
            "idem-1",
        )
    )
    assert result.external_publication_id == "ig-media-1"
    assert any("/ig-user-1/media" in c and "media_publish" not in c for c in calls)
    assert any("media_publish" in c for c in calls)


def test_rate_limit_error_maps_to_rate_limited(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 4, "message": "Too many calls"}})

    provider = _provider(handler, monkeypatch=monkeypatch)
    with pytest.raises(PublishRateLimited):
        asyncio.run(
            provider.publish(_payload(asset_public_url="https://cdn.example.com/x.jpg"), "idem-1")
        )


def test_transient_error_maps_to_recoverable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 2, "message": "Service busy"}})

    provider = _provider(handler, monkeypatch=monkeypatch)
    with pytest.raises(PublishRecoverableError):
        asyncio.run(
            provider.publish(_payload(asset_public_url="https://cdn.example.com/x.jpg"), "idem-1")
        )


def test_permission_error_maps_to_permanent(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": {"code": 200, "message": "Permissions error"}}
        )

    provider = _provider(handler, monkeypatch=monkeypatch)
    with pytest.raises(PublishPermanentError):
        asyncio.run(
            provider.publish(_payload(asset_public_url="https://cdn.example.com/x.jpg"), "idem-1")
        )


def test_get_status_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "555"})

    provider = _provider(handler, monkeypatch=monkeypatch)
    status = asyncio.run(provider.get_status("555"))
    assert status.status == "published"


def test_get_status_not_ready_raises(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "meta_publishing_enabled", False)
    provider = MetaPublishingProvider("token")
    with pytest.raises(PublishPermanentError):
        asyncio.run(provider.get_status("555"))
