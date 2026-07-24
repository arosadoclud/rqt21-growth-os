from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.ai import PromptTemplate
from app.models.enums import GenerationType
from app.utils.public_id import make as make_public_id


def _template(*, organization_id=None, generation_type=GenerationType.SOCIAL_POST, version="v1"):
    return PromptTemplate(
        public_id=make_public_id("pt"),
        organization_id=organization_id,
        name="Test template",
        generation_type=generation_type,
        version=version,
        system_instructions="system",
        user_template="user",
        output_schema={},
    )


def test_duplicate_system_template_rejected(db):
    db.add(_template(organization_id=None, version="dup-sys"))
    db.commit()

    db.add(_template(organization_id=None, version="dup-sys"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_duplicate_org_template_rejected(db, make_org):
    org = make_org("pt-org-a")
    db.add(_template(organization_id=org.id, version="dup-org"))
    db.commit()

    db.add(_template(organization_id=org.id, version="dup-org"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_same_version_allowed_across_different_orgs(db, make_org):
    org_a = make_org("pt-org-b")
    org_b = make_org("pt-org-c")
    db.add(_template(organization_id=org_a.id, version="shared-v1"))
    db.commit()
    db.add(_template(organization_id=org_b.id, version="shared-v1"))
    db.commit()  # must NOT raise — different orgs are independent


def test_system_and_org_template_can_share_version(db, make_org):
    """The whole point of the partial-index fix: a system template
    (organization_id IS NULL) and an org template can carry the same
    (generation_type, version) without colliding — they live in different
    partial indexes."""
    org = make_org("pt-org-d")
    db.add(_template(organization_id=None, version="shared-v2"))
    db.commit()
    db.add(_template(organization_id=org.id, version="shared-v2"))
    db.commit()  # must NOT raise


def test_multiple_system_templates_previously_allowed_now_rejected(db):
    """Regression test for the original bug: before the partial-index fix,
    Postgres treated every NULL organization_id as distinct, so this
    silently succeeded twice. It must now fail."""
    db.add(_template(organization_id=None, generation_type=GenerationType.REEL_SCRIPT, version="regression-v1"))
    db.commit()
    db.add(_template(organization_id=None, generation_type=GenerationType.REEL_SCRIPT, version="regression-v1"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_concurrent_inserts_only_one_survives(db):
    """Simulate two concurrent requests racing to create the same system
    template version: open a second, independent DB session/connection so
    the two INSERTs are genuinely concurrent transactions, not just two
    flushes on the same session."""
    from sqlalchemy.orm import sessionmaker

    from app.core.db import engine as app_engine

    Session2 = sessionmaker(bind=app_engine, autoflush=False, autocommit=False, future=True)
    db2 = Session2()
    try:
        db.add(_template(organization_id=None, version="race-v1"))
        db2.add(_template(organization_id=None, version="race-v1"))

        db.commit()
        with pytest.raises(IntegrityError):
            db2.commit()
        db2.rollback()
    finally:
        db2.close()


def test_get_active_template_lazily_creates_default_once(db, make_org):
    """get_active_template must be safe to call concurrently without
    violating the new partial index — it creates the default system
    template lazily on first use."""
    from app.ai.templates import get_active_template

    org = make_org("pt-org-lazy")
    t1 = get_active_template(db, org.id, GenerationType.CONTENT_IDEAS)
    t2 = get_active_template(db, org.id, GenerationType.CONTENT_IDEAS)
    assert t1.id == t2.id
