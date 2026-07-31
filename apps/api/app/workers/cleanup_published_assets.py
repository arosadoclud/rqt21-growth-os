"""One-shot worker: free R2/S3 storage space by deleting the file behind
any Asset whose only publications have already gone out.

Usage::

    uv run python -m app.workers.cleanup_published_assets

Meant to be invoked by an EXTERNAL scheduler (cron, a Railway/Render
scheduled job, a GitHub Actions cron) on a daily-or-so cadence — this
module does a single pass and exits, same pattern as
app.workers.publish_due. It does NOT delete anything immediately after
publishing: settings.asset_cleanup_after_days (default 2) is a grace
period, so an asset stays available for a couple of days after going out
in case something needs re-checking.

Never touches the Asset DB row's history — only the storage bytes get
deleted; the row survives with status=ARCHIVED so "what was published and
when" stays queryable. Storage delete-on-missing-key is a no-op for every
provider here, so re-running this against an already-archived asset (or a
double-processing race) is always safe.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app import audit
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.assets import Asset
from app.models.enums import AssetStatus, PublicationStatus
from app.models.publishing import Publication
from app.storage.provider import get_storage_provider

# Any publication in one of these statuses still needs the file — a
# READY/SCHEDULED/RETRY_SCHEDULED publish hasn't happened yet, and a
# FAILED one may still be retried or manually re-attempted. An asset is
# only a cleanup candidate once every publication referencing it has
# either succeeded (PUBLISHED) or been explicitly abandoned
# (CANCELLED/ARCHIVED).
_STILL_NEEDED_STATUSES = {
    PublicationStatus.DRAFT,
    PublicationStatus.READY,
    PublicationStatus.SCHEDULED,
    PublicationStatus.PUBLISHING,
    PublicationStatus.RETRY_SCHEDULED,
    PublicationStatus.FAILED,
}


def _claim(asset_id: uuid.UUID) -> bool:
    """Atomic conditional UPDATE, same pattern as publish_due._claim — only
    one concurrent run of this worker can win the race to archive (and
    then delete the storage object for) a given asset."""
    with SessionLocal() as db:
        result = db.execute(
            update(Asset)
            .where(Asset.id == asset_id, Asset.status == AssetStatus.READY)
            .values(status=AssetStatus.ARCHIVED)
        )
        db.commit()
        return result.rowcount == 1


def run_once() -> dict[str, int]:
    counts = {"deleted": 0, "skipped": 0}
    threshold = datetime.now(UTC) - timedelta(days=settings.asset_cleanup_after_days)

    with SessionLocal() as db:
        candidate_ids = (
            db.execute(select(Publication.asset_id).where(Publication.asset_id.is_not(None)).distinct())
            .scalars()
            .all()
        )

        for asset_id in candidate_ids:
            asset = db.get(Asset, asset_id)
            if asset is None or asset.status != AssetStatus.READY:
                continue

            pubs = db.execute(
                select(Publication).where(Publication.asset_id == asset_id)
            ).scalars().all()

            if any(p.status in _STILL_NEEDED_STATUSES for p in pubs):
                counts["skipped"] += 1
                continue

            published = [p for p in pubs if p.status == PublicationStatus.PUBLISHED]
            if not published:
                # Every reference is CANCELLED/ARCHIVED — nothing ever
                # actually went out, so this isn't what the job targets;
                # leave it for the regular asset library to manage.
                counts["skipped"] += 1
                continue

            latest_published_at = max(p.published_at or p.updated_at for p in published)
            if latest_published_at > threshold:
                counts["skipped"] += 1
                continue

            if not _claim(asset_id):
                counts["skipped"] += 1
                continue

            storage_provider = get_storage_provider()
            asyncio.run(storage_provider.delete(storage_key=asset.storage_key))

            audit.record(
                db,
                action="asset.storage_cleaned_up",
                organization_id=asset.organization_id,
                target_type="asset",
                target_id=asset.id,
                payload={
                    "published_publication_count": len(published),
                    "latest_published_at": latest_published_at.isoformat(),
                },
            )
            db.commit()
            counts["deleted"] += 1

    return counts


def main() -> None:
    result = run_once()
    print(f"[worker] cleanup_published_assets: {result}")


if __name__ == "__main__":
    main()
