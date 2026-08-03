"""PLAT-04：租户自动开通、初始化与上线验收。

Revision ID: 0167_tenant_provisioning
Revises: 0166_service_catalog
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0167_tenant_provisioning"
down_revision = "0166_service_catalog"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0167_tenant_provisioning requires MySQL")


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

    if not insp.has_table("t_provisioning_job"):
        op.create_table(
            "t_provisioning_job",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("tenant_code", sa.String(64), nullable=False),
            sa.Column("tenant_id", sa.BigInteger()),
            sa.Column("input_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("current_step", sa.String(40)),
            sa.Column("last_error", sa.String(1000)),
            sa.Column("requested_by", sa.BigInteger()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_provisioning_job_idempotency", "t_provisioning_job",
                                    ["idempotency_key"])
        op.create_index("ix_t_provisioning_job_tenant_id", "t_provisioning_job", ["tenant_id"])
        op.create_index("ix_t_provisioning_job_status", "t_provisioning_job", ["status"])

    if not insp.has_table("t_provisioning_step_run"):
        op.create_table(
            "t_provisioning_step_run",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.BigInteger(), nullable=False),
            sa.Column("step_code", sa.String(40), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_summary_json", sa.JSON()),
            sa.Column("error_message", sa.String(1000)),
            sa.Column("trace_id", sa.String(80)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_provisioning_step_scope", "t_provisioning_step_run",
                                    ["job_id", "step_code"])
        op.create_index("ix_t_provisioning_step_run_job_id", "t_provisioning_step_run", ["job_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_provisioning_step_run", "t_provisioning_job"):
        if insp.has_table(table):
            op.drop_table(table)
