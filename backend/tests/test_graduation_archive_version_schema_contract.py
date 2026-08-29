"""GD-018：归档版本 ORM 与 Alembic 公共审计列必须一致。"""
from __future__ import annotations

from pathlib import Path

from app.modules.graduation.services import graduation_package9_guard as package9


def test_archive_version_model_requires_common_actor_columns():
    columns = set(package9.GraduationArchiveVersion.__table__.columns.keys())
    assert {"created_by", "updated_by"}.issubset(columns)


def test_archive_version_audit_column_reconciliation_migration_is_chained_and_complete():
    migration = Path(
        "alembic/versions/20260824_gd_archive_version_audit_columns.py"
    ).read_text("utf-8")
    assert 'revision = "20260824_gd_arch_audit_cols"' in migration
    assert 'down_revision = "20260822_pr191_w7_main_merge"' in migration
    assert '"created_by": sa.Column("created_by", sa.BigInteger(), nullable=True)' in migration
    assert '"updated_by": sa.Column("updated_by", sa.BigInteger(), nullable=True)' in migration
    assert "op.add_column(_TABLE, column)" in migration
