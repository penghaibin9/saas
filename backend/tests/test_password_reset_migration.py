"""密码重置短信作业迁移必须兼容 0001 的 metadata.create_all 活基线。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


_MIGRATION = Path("alembic/versions/20260809_password_reset_sms_job.py")


def _load_migration():
    spec = importlib.util.spec_from_file_location("password_reset_sms_job", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_password_reset_migration_is_idempotent_when_live_baseline_created_table():
    engine = sa.create_engine("sqlite://")
    migration = _load_migration()
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE t_password_reset_sms_job (id INTEGER PRIMARY KEY)"
        ))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        assert "t_password_reset_sms_job" in sa.inspect(conn).get_table_names()


def test_password_reset_migration_creates_and_idempotently_drops_table():
    engine = sa.create_engine("sqlite://")
    migration = _load_migration()
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()
        assert "t_password_reset_sms_job" in sa.inspect(conn).get_table_names()
        migration.downgrade()
        migration.downgrade()
        assert "t_password_reset_sms_job" not in sa.inspect(conn).get_table_names()
