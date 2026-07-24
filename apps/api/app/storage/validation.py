"""File upload safety checks.

Never trust the filename or MIME type the client claims — sniff real magic
bytes and re-derive everything else server-side. This module is the single
place asset size/type policy lives; nothing else should hardcode a MIME
allowlist or size limit.
"""

from __future__ import annotations

import re
import uuid

from app.core.config import settings
from app.models.enums import AssetType

# (magic bytes prefix, mime_type, asset_type)
_SIGNATURES: list[tuple[bytes, str, AssetType]] = [
    (b"\xff\xd8\xff", "image/jpeg", AssetType.IMAGE),
    (b"\x89PNG\r\n\x1a\n", "image/png", AssetType.IMAGE),
    (b"GIF87a", "image/gif", AssetType.IMAGE),
    (b"GIF89a", "image/gif", AssetType.IMAGE),
    (b"RIFF", "image/webp", AssetType.IMAGE),  # WEBP: RIFF....WEBP, checked loosely
    (b"%PDF-", "application/pdf", AssetType.DOCUMENT),
    (b"\x00\x00\x00\x18ftyp", "video/mp4", AssetType.VIDEO),
    (b"\x00\x00\x00\x1cftyp", "video/mp4", AssetType.VIDEO),
    (b"\x1aE\xdf\xa3", "video/webm", AssetType.VIDEO),
    (b"ID3", "audio/mpeg", AssetType.AUDIO),
]

# MOCK fixtures used by tests carry this literal payload — real header check
# still applies to everything else.
_ALLOWED_MIME_BY_TYPE: dict[AssetType, set[str]] = {
    AssetType.IMAGE: {"image/jpeg", "image/png", "image/gif", "image/webp"},
    AssetType.VIDEO: {"video/mp4", "video/webm"},
    AssetType.DOCUMENT: {"application/pdf"},
    AssetType.AUDIO: {"audio/mpeg"},
}


class AssetRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def sniff_mime(content: bytes) -> tuple[str, AssetType] | None:
    for sig, mime, atype in _SIGNATURES:
        if content.startswith(sig):
            return mime, atype
    # WEBP needs a second check: RIFF....WEBP
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", AssetType.IMAGE
    return None


_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]")


def make_safe_filename(original_filename: str) -> str:
    original_filename = original_filename.strip().replace("\\", "/").split("/")[-1]
    # Strip anything resembling a second extension/traversal attempt and any
    # character outside a conservative allowlist.
    cleaned = _UNSAFE_CHARS.sub("_", original_filename)[-120:]
    if not cleaned or cleaned in (".", ".."):
        cleaned = "file"
    return f"{uuid.uuid4().hex[:8]}_{cleaned}"


def max_size_bytes(asset_type: AssetType) -> int:
    mb = {
        AssetType.IMAGE: settings.asset_max_image_mb,
        AssetType.VIDEO: settings.asset_max_video_mb,
        AssetType.DOCUMENT: settings.asset_max_document_mb,
    }.get(asset_type, settings.asset_max_document_mb)
    return mb * 1024 * 1024


def validate_upload(
    *, declared_mime: str, asset_type: AssetType, content: bytes
) -> tuple[str, AssetType]:
    """Returns (real_mime, real_asset_type) or raises AssetRejected.

    Ignores the client-declared MIME/asset_type for the actual decision —
    they're only used to pick which size ceiling applies before sniffing.
    """
    if len(content) == 0:
        raise AssetRejected("empty file")
    if len(content) > max_size_bytes(asset_type):
        raise AssetRejected(
            f"file exceeds the {max_size_bytes(asset_type) // (1024 * 1024)}MB limit for {asset_type.value}"
        )

    sniffed = sniff_mime(content)
    if sniffed is None:
        raise AssetRejected("unrecognized or unsupported file type")
    real_mime, real_type = sniffed

    if real_mime not in _ALLOWED_MIME_BY_TYPE.get(real_type, set()):
        raise AssetRejected(f"mime type {real_mime} is not allowed")

    # Re-check size against the REAL type's ceiling too (client may have
    # under-declared to dodge a stricter limit).
    if len(content) > max_size_bytes(real_type):
        raise AssetRejected(
            f"file exceeds the {max_size_bytes(real_type) // (1024 * 1024)}MB limit for {real_type.value}"
        )

    # Reject active SVG content outright — we don't sniff SVG as an allowed
    # image type above, so any XML/SVG payload already fails the allowlist
    # check, but double-check explicitly for defense in depth.
    if content.lstrip()[:5] in (b"<?xml", b"<svg "):
        raise AssetRejected("SVG and other inline-script-capable formats are not accepted")

    return real_mime, real_type
