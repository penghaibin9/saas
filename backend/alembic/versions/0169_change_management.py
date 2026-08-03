"""PLAT-11：变更、发布、兼容性、灰度与回滚。

Revision ID: 0169_change_management
Revises: 0168_incident
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0169_change_management"
down_revision = "0168_incident"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0169_change_management requires MySQL")


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

    if not insp.has_table("t_change_request"):
        op.create_table(
            "t_change_request",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("change_type", sa.String(24), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("is_emergency", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_irreversible", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("git_sha", sa.String(64)),
            sa.Column("pr_url", sa.String(500)),
            sa.Column("ci_evidence_json", sa.JSON()),
            sa.Column("min_client_version", sa.String(30)),
            sa.Column("package_codes_json", sa.JSON()),
            sa.Column("affected_service_codes_json", sa.JSON(), nullable=False),
            sa.Column("rollback_plan", sa.String(2000)),
            sa.Column("requested_by", sa.BigInteger()),
            sa.Column("approved_by", sa.BigInteger()),
            sa.Column("approved_at", sa.DateTime()),
            sa.Column("scheduled_at", sa.DateTime()),
            sa.Column("verified_at", sa.DateTime()),
            sa.Column("rolled_back_at", sa.DateTime()),
            sa.Column("last_error", sa.String(1000)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_change_request_status", "t_change_request", ["status"])

    if not insp.has_table("t_change_impact"):
        op.create_table(
            "t_change_impact",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("change_id", sa.BigInteger(), nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("impact_type", sa.String(10), nullable=False),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_change_impact_scope", "t_change_impact",
                                    ["change_id", "tenant_id"])
        op.create_index("ix_t_change_impact_change_id", "t_change_impact", ["change_id"])

    if not insp.has_table("t_change_execution"):
        op.create_table(
            "t_change_execution",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("change_id", sa.BigInteger(), nullable=False),
            sa.Column("wave_no", sa.Integer(), nullable=False),
            sa.Column("tenant_ids_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("finished_at", sa.DateTime()),
            sa.Column("error_message", sa.String(1000)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_change_execution_wave", "t_change_execution",
                                    ["change_id", "wave_no"])
        op.create_index("ix_t_change_execution_change_id", "t_change_execution", ["change_id"])

    if not insp.has_table("t_maintenance_window"):
        op.create_table(
            "t_maintenance_window",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("start_at", sa.DateTime(), nullable=False),
            sa.Column("end_at", sa.DateTime(), nullable=False),
            sa.Column("reason", sa.String(500)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_maintenance_window_range", "t_maintenance_window",
                        ["start_at", "end_at"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_maintenance_window", "t_change_execution", "t_change_impact", "t_change_request"):
        if insp.has_table(table):
            op.drop_table(table)
