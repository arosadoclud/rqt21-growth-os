"""Very small User-Agent classifier.

We only need coarse buckets for analytics. This avoids adding a heavyweight
dependency; if we ever need real UA parsing we'll switch to `ua-parser`.
"""

from __future__ import annotations


def classify(ua: str | None) -> tuple[str | None, str | None, str | None]:
    """Return (device_type, browser, os) as coarse buckets."""
    if not ua:
        return None, None, None
    low = ua.lower()

    if "mobile" in low or "iphone" in low or "android" in low:
        device = "mobile"
    elif "tablet" in low or "ipad" in low:
        device = "tablet"
    else:
        device = "desktop"

    if "edg/" in low:
        browser = "edge"
    elif "chrome/" in low and "chromium" not in low:
        browser = "chrome"
    elif "firefox/" in low:
        browser = "firefox"
    elif "safari/" in low and "chrome/" not in low:
        browser = "safari"
    else:
        browser = "other"

    if "windows" in low:
        os = "windows"
    elif "mac os" in low or "macintosh" in low:
        os = "macos"
    elif "android" in low:
        os = "android"
    elif "iphone" in low or "ipad" in low or "ios" in low:
        os = "ios"
    elif "linux" in low:
        os = "linux"
    else:
        os = "other"

    return device, browser, os
