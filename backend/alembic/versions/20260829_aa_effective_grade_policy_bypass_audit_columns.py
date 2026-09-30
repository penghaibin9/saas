"""Reconcile CommonMixin audit columns on effective-grade policy bypass.

Revision ID: 20260829_aa_bypass_audit_cols
Revises: 20260829_role_assign_scope
Create Date: 2026-08-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260829_aa_bypass_audit_cols"
down_revision = "20260829_role_assign_scope"
branch_labels = None
depends_on = None

_TABLE = "t_aa_effective_grade_policy_bypass"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260829_aa_bypass_audit_cols requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    columns = {row["name"] for row in inspect(bind).get_columns(_TABLE)}

    if "created_by" not in columns:
        op.add_column(_TABLE, sa.Column("created_by", sa.BigInteger(), nullable=True))
    if "updated_by" not in columns:
        op.add_column(_TABLE, sa.Column("updated_by", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    columns = {row["name"] for row in inspect(bind).get_columns(_TABLE)}

    if "updated_by" in columns:
        op.drop_column(_TABLE, "updated_by")
    if "created_by" in columns:
        op.drop_column(_TABLE, "created_by")
