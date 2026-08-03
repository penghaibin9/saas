"""PLAT-08：服务目录、依赖与租户影响地图。

Revision ID: 0166_service_catalog
Revises: 73e91b9e47af
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0166_service_catalog"
down_revision = "73e91b9e47af"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0166_service_catalog requires MySQL")


def _common() -> list:
    return [
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

    if not insp.has_table("t_platform_service"):
        op.create_table(
            "t_platform_service",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("service_code", sa.String(64), nullable=False),
            sa.Column("service_name", sa.String(200), nullable=False),
            sa.Column("tier", sa.String(10), nullable=False, server_default="P2"),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("owner_user_id", sa.BigInteger()),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("responders_json", sa.JSON()),
            sa.Column("approvers_json", sa.JSON()),
            sa.Column("runbook_url", sa.String(500)),
            sa.Column("monitoring_url", sa.String(500)),
            sa.Column("slo_target", sa.String(50)),
            sa.Column("description", sa.String(1000)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_platform_service_code", "t_platform_service", ["service_code"])
        op.create_index("ix_t_platform_service_code", "t_platform_service", ["service_code"])

    if not insp.has_table("t_service_dependency"):
        op.create_table(
            "t_service_dependency",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("service_code", sa.String(64), nullable=False),
            sa.Column("depends_on_service_code", sa.String(64), nullable=False),
            sa.Column("dependency_type", sa.String(10), nullable=False, server_default="HARD"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_service_dependency_edge", "t_service_dependency",
                                    ["service_code", "depends_on_service_code"])
        op.create_index("ix_t_service_dependency_service_code", "t_service_dependency", ["service_code"])
        op.create_index("ix_t_service_dependency_depends_on", "t_service_dependency",
                        ["depends_on_service_code"])

    if not insp.has_table("t_service_tenant_usage"):
        op.create_table(
            "t_service_tenant_usage",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("service_code", sa.String(64), nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("usage_status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("last_used_at", sa.DateTime()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_service_tenant_usage", "t_service_tenant_usage",
                                    ["service_code", "tenant_id"])
        op.create_index("ix_t_service_tenant_usage_service_code", "t_service_tenant_usage",
                        ["service_code"])
        op.create_index("ix_t_service_tenant_usage_tenant_id", "t_service_tenant_usage",
                        ["tenant_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_service_tenant_usage", "t_service_dependency", "t_platform_service"):
        if insp.has_table(table):
            op.drop_table(table)
