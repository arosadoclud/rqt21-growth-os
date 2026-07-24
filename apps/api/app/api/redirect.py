"""Public short-code redirect and click tracking.

Mounted at the app root at ``/r/{short_code}``, outside the ``/api/v1`` tree so
it is trivially reachable by any social platform. This endpoint is:

- Unauthenticated.
- Not subject to CSRF (safe method + public consumers).
- Not subject to rate limiting yet (would be added in Phase 6 once we see real
  bot traffic patterns).

What we log per click, and why:
- occurred_at, tracking_link_id, organization_id: fundamental to the funnel.
- referrer, user_agent (truncated): source attribution and coarse UA analytics.
- ip_hash (HMAC-SHA256 with server secret): count unique visitors without
  storing the actual address. See ``app.utils.ip_hash``.
- device_type/browser/os: derived from user_agent, coarse buckets only.
- query_params (JSON): anything extra the SPA passed along (e.g. content_id).

What we do NOT log: plain IP, third-party cookies, precise geolocation,
canvas/audio fingerprint. See privacy notes in the README.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import rate_limit
from app.core.db import SessionLocal
from app.models.click import ClickEvent
from app.models.tracking import TrackingLink
from app.utils.ip_hash import hash_ip
from app.utils.ua import classify

router = APIRouter(tags=["public-redirect"])


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _apply_utm(destination: str, link: TrackingLink) -> str:
    parsed = urlparse(destination)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for k, v in {
        "utm_source": link.utm_source,
        "utm_medium": link.utm_medium,
        "utm_campaign": link.utm_campaign,
        "utm_content": link.utm_content,
        "utm_term": link.utm_term,
    }.items():
        if v:
            existing[k] = v
    return urlunparse(parsed._replace(query=urlencode(existing, doseq=True)))


_TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}


@router.get("/r/{short_code}")
def redirect(short_code: str, request: Request) -> RedirectResponse:
    rate_limit.check_public_redirect(request)
    with SessionLocal() as db:
        link = db.execute(
            select(TrackingLink).where(TrackingLink.short_code == short_code)
        ).scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="link not found"
            )
        if not link.is_active:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="link is inactive"
            )
        if link.expires_at is not None and link.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="link has expired"
            )

        ua_raw = request.headers.get("user-agent", "")[:500] or None
        device, browser, os_name = classify(ua_raw)
        ref = request.headers.get("referer")
        ref = ref[:1000] if ref else None
        query_params = {
            k: v[0] if len(v) == 1 else v
            for k, v in parse_qs(request.url.query, keep_blank_values=True).items()
            if k not in _TRACKING_KEYS
        }

        db.add(
            ClickEvent(
                organization_id=link.organization_id,
                tracking_link_id=link.id,
                referrer=ref,
                user_agent=ua_raw,
                ip_hash=hash_ip(_client_ip(request)),
                device_type=device,
                browser=browser,
                os=os_name,
                query_params=query_params,
            )
        )
        db.commit()
        final = _apply_utm(link.destination_url, link)

    return RedirectResponse(url=final, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
