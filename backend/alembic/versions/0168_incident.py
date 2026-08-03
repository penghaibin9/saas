"""PLAT-09：事件、状态页与统一学校通知。

Revision ID: 0168_incident
Revises: 0167_tenant_provisioning
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0168_incident"
down_revision = "0167_tenant_provisioning"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0168_incident requires MySQL")


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

    if not insp.has_table("t_incident"):
        op.create_table(
            "t_incident",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("severity", sa.String(10), nullable=False, server_default="P2"),
            sa.Column("status", sa.String(20), nullable=False, server_default="DETECTED"),
            sa.Column("affected_service_codes_json", sa.JSON(), nullable=False),
            sa.Column("commander_user_id", sa.BigInteger()),
            sa.Column("commander_name", sa.String(100)),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("problem_conversion_requested_at", sa.DateTime()),
            sa.Column("problem_conversion_requested_by", sa.BigInteger()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_incident_status", "t_incident", ["status"])

    if not insp.has_table("t_incident_tenant"):
        op.create_table(
            "t_incident_tenant",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("incident_id", sa.BigInteger(), nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("impact_type", sa.String(10), nullable=False),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_incident_tenant_scope", "t_incident_tenant",
                                    ["incident_id", "tenant_id"])
        op.create_index("ix_t_incident_tenant_incident_id", "t_incident_tenant", ["incident_id"])
        op.create_index("ix_t_incident_tenant_tenant_id", "t_incident_tenant", ["tenant_id"])

    if not insp.has_table("t_incident_update"):
        op.create_table(
            "t_incident_update",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("incident_id", sa.BigInteger(), nullable=False),
            sa.Column("update_seq", sa.Integer(), nullable=False),
            sa.Column("status_at_update", sa.String(20), nullable=False),
            sa.Column("internal_note", sa.String(2000)),
            sa.Column("external_message", sa.String(1000), nullable=False),
            sa.Column("template_version", sa.String(20), nullable=False, server_default="v1"),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("notification_result_json", sa.JSON()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_incident_update_seq", "t_incident_update",
                                    ["incident_id", "update_seq"])
        op.create_index("ix_t_incident_update_incident_id", "t_incident_update", ["incident_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_incident_update", "t_incident_tenant", "t_incident"):
        if insp.has_table(table):
            op.drop_table(table)
