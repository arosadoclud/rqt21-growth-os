"""Centralized per-platform publishing rules.

Every numeric limit or requirement used to validate a Publication lives here
— nowhere else hardcodes a caption length or hashtag count. Platforms not
fully wired up yet (TikTok, Pinterest, YouTube, LinkedIn) still get a rule
row so validation returns a clear "adapter not active" message instead of
silently pretending to support them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import Platform, PublicationType


@dataclass(frozen=True)
class PlatformRule:
    platform: Platform
    active: bool
    supported_types: tuple[PublicationType, ...]
    caption_max_len: int
    hashtag_max_count: int
    requires_asset: bool
    requires_alt_text_for_images: bool
    recommended_dimensions: dict[str, str] = field(default_factory=dict)
    notes: str = ""


PLATFORM_RULES: dict[Platform, PlatformRule] = {
    Platform.INSTAGRAM: PlatformRule(
        platform=Platform.INSTAGRAM,
        active=True,
        supported_types=(
            PublicationType.POST,
            PublicationType.REEL,
            PublicationType.STORY,
            PublicationType.CAROUSEL,
        ),
        caption_max_len=2200,
        hashtag_max_count=30,
        requires_asset=True,
        requires_alt_text_for_images=True,
        recommended_dimensions={
            "REEL": "1080x1920 (9:16)",
            "POST": "1080x1350 (4:5) or 1080x1080 (1:1)",
            "STORY": "1080x1920 (9:16)",
        },
        notes="Reels should use a vertical video asset; feed posts accept "
        "square or portrait images.",
    ),
    Platform.FACEBOOK: PlatformRule(
        platform=Platform.FACEBOOK,
        active=True,
        supported_types=(PublicationType.POST, PublicationType.VIDEO),
        caption_max_len=63206,
        hashtag_max_count=30,
        requires_asset=False,
        requires_alt_text_for_images=True,
        recommended_dimensions={"POST": "1200x630 (link) or 1080x1080 (image)"},
        notes="Image or video post; a destination link is optional.",
    ),
    Platform.TIKTOK: PlatformRule(
        platform=Platform.TIKTOK,
        active=False,
        supported_types=(),
        caption_max_len=2200,
        hashtag_max_count=0,
        requires_asset=True,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.WEB: PlatformRule(
        platform=Platform.WEB,
        active=False,
        supported_types=(),
        caption_max_len=0,
        hashtag_max_count=0,
        requires_asset=False,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.YOUTUBE: PlatformRule(
        platform=Platform.YOUTUBE,
        active=False,
        supported_types=(),
        caption_max_len=5000,
        hashtag_max_count=15,
        requires_asset=True,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.WHATSAPP: PlatformRule(
        platform=Platform.WHATSAPP,
        active=False,
        supported_types=(),
        caption_max_len=1024,
        hashtag_max_count=0,
        requires_asset=False,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.EMAIL: PlatformRule(
        platform=Platform.EMAIL,
        active=False,
        supported_types=(PublicationType.EMAIL,),
        caption_max_len=0,
        hashtag_max_count=0,
        requires_asset=False,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.META_ADS: PlatformRule(
        platform=Platform.META_ADS,
        active=False,
        supported_types=(),
        caption_max_len=0,
        hashtag_max_count=0,
        requires_asset=False,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
    Platform.OTHER: PlatformRule(
        platform=Platform.OTHER,
        active=False,
        supported_types=(),
        caption_max_len=0,
        hashtag_max_count=0,
        requires_asset=False,
        requires_alt_text_for_images=False,
        notes="Adapter not active in this deployment.",
    ),
}

# Platforms defined via the PINTEREST/LINKEDIN/TIKTOK EditorialPlatform enum
# but absent from the growth-domain Platform enum are represented purely at
# the editorial-calendar layer (Phase 3) and are out of scope for Publication
# validation until Publication.platform grows to include them.


def get_rule(platform: Platform) -> PlatformRule:
    return PLATFORM_RULES.get(platform, PLATFORM_RULES[Platform.OTHER])
