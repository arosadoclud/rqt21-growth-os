import asyncio

from app.core.db import SessionLocal
from app.models.publishing import PublishingConnection
from app.publishing.meta_token_resolver import (
    resolve_connection_access_token,
    verify_meta_account_reachable,
)


def main():
    db = SessionLocal()
    try:
        row = db.query(PublishingConnection).filter_by(public_id='pcn_i5gzdqb8').one_or_none()
        if not row:
            print('connection not found')
            return
        print('found', row.public_id, row.provider, row.platform, row.external_account_id)
        token = asyncio.run(resolve_connection_access_token(row))
        print('resolved_token_present', bool(token))
        if token:
            try:
                asyncio.run(verify_meta_account_reachable(token, row.external_account_id or ''))
                print('verify: success')
            except Exception as e:
                print('verify: failed', type(e).__name__, str(e)[:300])
    finally:
        db.close()

if __name__ == '__main__':
    main()
