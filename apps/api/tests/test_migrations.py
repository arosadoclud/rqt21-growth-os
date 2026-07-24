from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_migrations_from_empty(tmp_path):
    """Run alembic upgrade head against a scratch schema, then downgrade base."""
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    url = os.environ.get("TEST_DATABASE_URL", settings.database_url)
    scratch = "rqt_mig_test"
    parent_url = url.rsplit("/", 1)[0] + "/postgres"
    parent = create_engine(parent_url, isolation_level="AUTOCOMMIT")
    with parent.begin() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))
        c.execute(text(f"CREATE DATABASE {scratch}"))

    scratch_url = url.rsplit("/", 1)[0] + f"/{scratch}"
    api_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = scratch_url

    up = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=api_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    down = subprocess.run(
        ["alembic", "downgrade", "base"],
        cwd=api_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    with parent.begin() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))
