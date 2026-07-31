import asyncio

from app.core.db import SessionLocal
from app.models.publishing import PublishingConnection
from app.publishing.adapters import MetaPublishingProvider, PublicationPayload
from app.publishing.meta_token_resolver import resolve_connection_access_token


def main():
    db = SessionLocal()
    try:
        row = db.query(PublishingConnection).filter_by(public_id='pcn_i5gzdqb8').one_or_none()
        if not row:
            print('connection not found')
            return
        print('using connection', row.public_id, row.platform, row.external_account_id)
        token = asyncio.run(resolve_connection_access_token(row))
        print('resolved token present:', bool(token))
        provider = MetaPublishingProvider(access_token=token)
        payload = PublicationPayload(
            publication_id='sim-pub-1',
            platform='FACEBOOK',
            publication_type='POST',
            caption='Simulate publish attempt',
            title='SIM TEST',
            cta=None,
            hashtags=[],
            asset_storage_key=None,
            connection_external_account_id=row.external_account_id,
            asset_public_url=None,
            thumbnail_public_url=None,
        )
        try:
            result = asyncio.run(provider.publish(payload, idempotency_key='sim-1'))
            print('publish result:', result)
        except Exception as e:
            print('publish exception:', type(e).__name__, str(e)[:500])
    finally:
        db.close()

if __name__ == '__main__':
    main()
