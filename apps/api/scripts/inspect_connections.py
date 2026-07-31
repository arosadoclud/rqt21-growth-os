from app.core.db import SessionLocal
from app.models.publishing import PublishingConnection
from app.publishing.crypto import decrypt_credentials, last_four


def main():
    db = SessionLocal()
    try:
        rows = db.query(PublishingConnection).all()
        if not rows:
            print("No publishing connections found in DB.")
            return
        for r in rows:
            print("---")
            print("id:", r.id)
            print("public_id:", r.public_id)
            print("provider:", r.provider)
            print("platform:", r.platform)
            print("external_account_id:", r.external_account_id)
            if r.credentials_encrypted:
                try:
                    creds = decrypt_credentials(r.credentials_encrypted)
                    print("credentials_last_four:", last_four(creds))
                    print("credentials_keys:", list(creds.keys()))
                except Exception as e:
                    print("credentials: couldn't decrypt:", e)
            else:
                print("credentials: none")
    finally:
        db.close()


if __name__ == '__main__':
    main()
