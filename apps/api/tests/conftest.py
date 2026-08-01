from __future__ import annotations

import os
from collections.abc import Generator

import pytest

# Set env BEFORE importing app modules so pydantic-settings picks them up.
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://rqt:rqt@localhost:5433/rqt_test",
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
# Long, high-entropy secret so PyJWT does not emit InsecureKeyLengthWarning.
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-abcdefghijklmnopqrstuvwxyz-0123456789-0123456789-XYZ",
)
os.environ.setdefault("RL_LOGIN_IP_LIMIT", "1000")
os.environ.setdefault("RL_LOGIN_EMAIL_LIMIT", "1000")
os.environ.setdefault("RL_REFRESH_IP_LIMIT", "1000")
# Never let tests touch disk/network for asset storage — MOCK is fully offline.
os.environ.setdefault("STORAGE_PROVIDER", "MOCK")
# Force MOCK regardless of a real AI_PROVIDER/AI_IMAGE_PROVIDER/API key in a
# local apps/api/.env (pydantic-settings' env_file discovery would otherwise
# pick those up here too) — tests must never call a real AI provider.
os.environ["AI_PROVIDER"] = "MOCK"
os.environ["AI_IMAGE_PROVIDER"] = "MOCK"
os.environ["AI_TTS_PROVIDER"] = "MOCK"
os.environ["AI_VIDEO_SCENE_SOURCE"] = "IMAGES"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["PEXELS_API_KEY"] = ""
# Auto-approval must stay opt-in per test via monkeypatch, not leak in from
# a local apps/api/.env — otherwise every submit-review test silently runs
# through the auto-review agent instead of the plain manual flow.
os.environ["ENABLE_AUTO_APPROVAL"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app import rate_limit  # noqa: E402
from app.core.db import engine as app_engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.csrf import CSRF_COOKIE, CSRF_HEADER  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.membership import Membership, Role  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.user import User  # noqa: E402

TestSession = sessionmaker(bind=app_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _prepare_schema() -> Generator[None, None, None]:
    with app_engine.begin() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        # Populate alembic_version so /ready reports healthy.
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num varchar(32) primary key)"))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0013_headline_schedule')"))
    yield
    with app_engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture(autouse=True)
def _clean_tables() -> Generator[None, None, None]:
    rate_limit.reset()
    with app_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


class AuthedClient(TestClient):
    """TestClient that automatically echoes the CSRF cookie into the header
    on every mutating request. Mirrors what the SPA does in the browser."""

    def request(self, method, url, **kwargs):  # type: ignore[override]
        if method.upper() not in ("GET", "HEAD", "OPTIONS"):
            csrf = self.cookies.get(CSRF_COOKIE)
            if csrf:
                headers = kwargs.get("headers")
                if headers is None:
                    headers = {}
                elif not isinstance(headers, dict):
                    headers = dict(headers)
                headers.setdefault(CSRF_HEADER, csrf)
                kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture
def client() -> Generator[AuthedClient, None, None]:
    with AuthedClient(app) as c:
        yield c


@pytest.fixture
def raw_client() -> Generator[TestClient, None, None]:
    """Client that does NOT auto-add CSRF headers. Used to test CSRF failures."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db: Session):
    def _make(email: str, password: str = "Password1!", name: str = "Test User") -> User:
        user = User(email=email.lower(), full_name=name, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def make_org(db: Session):
    def _make(slug: str, name: str | None = None) -> Organization:
        org = Organization(slug=slug, name=name or slug.upper())
        db.add(org)
        db.commit()
        db.refresh(org)
        return org

    return _make


@pytest.fixture
def add_member(db: Session):
    def _add(user: User, org: Organization, role: Role) -> Membership:
        m = Membership(user_id=user.id, organization_id=org.id, role=role)
        db.add(m)
        db.commit()
        db.refresh(m)
        return m

    return _add


@pytest.fixture
def login(client: AuthedClient):
    def _login(email: str, password: str = "Password1!") -> AuthedClient:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return client

    return _login


@pytest.fixture
def bootstrap(client: AuthedClient, db: Session, make_user, make_org, add_member, login):
    """Log in as a fresh OWNER of a fresh org and return (client, org_id, user)."""
    import uuid as _u

    from app.models.membership import Role as _Role

    def _bootstrap(role: _Role = _Role.OWNER, email: str | None = None):
        tag = _u.uuid4().hex[:8]
        email = email or f"boot-{tag}@example.com"
        user = make_user(email)
        org = make_org(f"boot-org-{tag}")
        add_member(user, org, role)
        c = AuthedClient(app)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 200, r.text
        c.headers["X-Organization-Id"] = str(org.id)
        return c, org.id, user

    return _bootstrap
