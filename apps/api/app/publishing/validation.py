"""Pre-publish validation: platform rules + asset readiness + approval gates.

Combines the centralized PlatformRule with the current Asset/ContentItem
state to decide whether a Publication is allowed to move to READY or be
sent to a provider. Nothing here mutates state — callers act on the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.assets import Asset
from app.models.enums import AssetStatus, AssetType, Platform, PublicationType
from app.publishing.platform_rules import get_rule


@dataclass(frozen=True)
class PublicationValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_publication_draft(
    *,
    platform: Platform,
    publication_type: PublicationType,
    caption: str,
    hashtags: list[str],
    asset: Asset | None,
) -> PublicationValidation:
    rule = get_rule(platform)
    errors: list[str] = []
    warnings: list[str] = []

    if not rule.active:
        errors.append(f"{platform.value} adapter is not active in this deployment")
        return PublicationValidation(ok=False, errors=errors)

    if publication_type not in rule.supported_types:
        errors.append(
            f"{publication_type.value} is not supported on {platform.value}"
        )

    if len(caption) > rule.caption_max_len:
        errors.append(
            f"caption exceeds the {rule.caption_max_len}-character limit for {platform.value}"
        )

    if len(hashtags) > rule.hashtag_max_count:
        errors.append(
            f"too many hashtags ({len(hashtags)} > {rule.hashtag_max_count} allowed)"
        )

    if rule.requires_asset and asset is None:
        errors.append(f"{platform.value} requires an asset")

    if asset is not None:
        if asset.status != AssetStatus.READY:
            errors.append("attached asset is not READY")
        if (
            rule.requires_alt_text_for_images
            and asset.asset_type == AssetType.IMAGE
            and not (asset.alt_text or "").strip()
        ):
            errors.append("alt text is required for images used in publications")
        if asset.asset_type == AssetType.VIDEO and asset.duration_seconds is None:
            warnings.append(
                "video duration could not be detected — verify it meets platform limits manually"
            )

    return PublicationValidation(ok=not errors, errors=errors, warnings=warnings)
