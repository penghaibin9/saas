"""PLAT-13：租户用量、容量、成本与公平使用。

Revision ID: 0172_tenant_metering
Revises: 0171_problem_management
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0172_tenant_metering"
down_revision = "0171_problem_management"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0172_tenant_metering requires MySQL")


def _common() -> list:
    return [
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_tenant_usage_snapshot"):
        op.create_table(
            "t_tenant_usage_snapshot",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("audit_event_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("file_upload_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("storage_total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("student_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("user_count", sa.Integer(), nullable=False, server_default="0"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_tenant_usage_snapshot_day", "t_tenant_usage_snapshot",
                                    ["tenant_id", "snapshot_date"])
        op.create_index("ix_t_tenant_usage_snapshot_date", "t_tenant_usage_snapshot", ["snapshot_date"])

    if not insp.has_table("t_tenant_fair_use_limit"):
        op.create_table(
            "t_tenant_fair_use_limit",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("resource_code", sa.String(40), nullable=False),
            sa.Column("daily_limit", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_tenant_fair_use_limit_resource", "t_tenant_fair_use_limit",
                                    ["tenant_id", "resource_code"])

    if not insp.has_table("t_tenant_fair_use_violation"):
        op.create_table(
            "t_tenant_fair_use_violation",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("resource_code", sa.String(40), nullable=False),
            sa.Column("violation_date", sa.Date(), nullable=False),
            sa.Column("actual_value", sa.BigInteger(), nullable=False),
            sa.Column("limit_value", sa.BigInteger(), nullable=False),
            sa.Column("action_taken", sa.String(20), nullable=False, server_default="LOGGED"),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_tenant_fair_use_violation_resource", "t_tenant_fair_use_violation",
                        ["resource_code"])
        op.create_index("ix_t_tenant_fair_use_violation_date", "t_tenant_fair_use_violation",
                        ["violation_date"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_tenant_fair_use_violation", "t_tenant_fair_use_limit", "t_tenant_usage_snapshot"):
        if insp.has_table(table):
            op.drop_table(table)
