import os
import subprocess
import sys
import uuid

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.db.session import make_engine
from tests.conftest import TEST_URL


def _run(url, *args):
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run([sys.executable, "-m", "alembic", *args], env=env, capture_output=True, text=True)


def test_migrations_apply_and_match_models(tmp_path):
    u = make_url(TEST_URL)
    name = f"mig_{uuid.uuid4().hex[:8]}"
    if u.drivername.startswith("sqlite"):
        url, admin = f"sqlite:///{tmp_path}/m.db", None
    else:
        admin = make_engine(u.set(database="postgres").render_as_string(hide_password=False)).execution_options(isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
        url = u.set(database=name).render_as_string(hide_password=False)
    try:
        up = _run(url, "upgrade", "head")
        assert up.returncode == 0, up.stderr
        tables = set(inspect(make_engine(url)).get_table_names())
        assert {"users", "workspaces", "memberships", "business_profiles", "campaigns", "content_versions",
                "approval_requests", "execution_records", "audit_events", "integrations"} <= tables
        chk = _run(url, "check")
        assert chk.returncode == 0, chk.stdout + chk.stderr  # models and migrations agree
    finally:
        if admin is not None:
            with admin.connect() as c:
                c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
