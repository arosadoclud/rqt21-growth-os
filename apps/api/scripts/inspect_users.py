from app.core.db import SessionLocal
from app.models.membership import Membership
from app.models.user import User


def main():
    db = SessionLocal()
    try:
        users = db.query(User).limit(5).all()
        print('users', len(users))
        for u in users:
            print('user', u.id, u.email, u.is_active)
        memberships = db.query(Membership).limit(10).all()
        print('memberships', len(memberships))
        for m in memberships:
            print('membership', m.user_id, m.organization_id, m.role)
    finally:
        db.close()


if __name__ == '__main__':
    main()
