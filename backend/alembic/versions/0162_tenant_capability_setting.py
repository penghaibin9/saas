"""SYS-13：学校能力启用设置（结构化，单键乐观锁）。

Revision ID: 0162_tenant_capability_setting
Revises: 0161_access_governance
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0162_tenant_capability_setting"
down_revision = "0161_access_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0162_tenant_capability_setting requires MySQL")


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_tenant_capability_setting"):
        op.create_table(
            "t_tenant_capability_setting",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("capability_key", sa.String(64), nullable=False,
                      comment="module-manifest.moduleKey"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("reason", sa.String(500), comment="最近一次启停原因，写入审计"),
            sa.Column("expires_at", sa.DateTime(), comment="学校自定义启用期限，到期视同停用"),
            sa.Column("last_changed_at", sa.DateTime()),
            sa.Column("last_changed_by", sa.BigInteger()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_tenant_capability_setting_tenant_id",
                        "t_tenant_capability_setting", ["tenant_id"])
        op.create_unique_constraint("uk_tenant_capability", "t_tenant_capability_setting",
                                    ["tenant_id", "capability_key"])
        op.create_index("idx_tenant_capability_enabled", "t_tenant_capability_setting",
                        ["tenant_id", "enabled"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if insp.has_table("t_tenant_capability_setting"):
        op.drop_table("t_tenant_capability_setting")
