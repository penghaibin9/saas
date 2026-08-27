"""补齐毕业设计归档版本表的公共审计主体列。

Revision ID: 20260824_gd_arch_audit_cols
Revises: 20260822_pr191_w7_main_merge
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260824_gd_arch_audit_cols"
down_revision = "20260822_pr191_w7_main_merge"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_TABLE = "t_gd_archive_version"
_REQUIRED_ACTOR_COLUMNS = {
    "created_by": sa.Column("created_by", sa.BigInteger(), nullable=True),
    "updated_by": sa.Column("updated_by", sa.BigInteger(), nullable=True),
}


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260824_gd_arch_audit_cols requires MySQL")


def _column_names() -> set[str]:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if _TABLE not in tables:
        raise RuntimeError(f"{_TABLE} is missing before audit-column reconciliation")
    return {str(row["name"]) for row in inspect(bind).get_columns(_TABLE)}


def upgrade() -> None:
    _require_mysql()
    existing = _column_names()
    for name, column in _REQUIRED_ACTOR_COLUMNS.items():
        if name not in existing:
            op.add_column(_TABLE, column)


def downgrade() -> None:
    _require_mysql()
    existing = _column_names()
    for name in ("updated_by", "created_by"):
        if name in existing:
            op.drop_column(_TABLE, name)
