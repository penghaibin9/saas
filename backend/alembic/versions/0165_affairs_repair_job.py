"""SA-P0-04：学工申诉补偿租约任务。

Revision ID: 0165_affairs_repair_job
Revises: 0164_master_data_governance
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0165_affairs_repair_job"
down_revision = "0164_master_data_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0165_affairs_repair_job requires MySQL")


def upgrade() -> None:
    _require_mysql()
    if inspect(op.get_bind()).has_table("t_affairs_repair_job"):
        return
    op.create_table(
        "t_affairs_repair_job",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("todo_type", sa.String(64), nullable=False),
        sa.Column("source_row_id", sa.BigInteger(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("last_error", sa.String(500)),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_t_affairs_repair_job_tenant_id", "t_affairs_repair_job", ["tenant_id"])
    op.create_unique_constraint("uk_affairs_repair_tenant_dedup", "t_affairs_repair_job", ["tenant_id", "dedup_key"])
    op.create_index("idx_affairs_repair_runnable", "t_affairs_repair_job", ["tenant_id", "state", "next_run_at"])
    op.create_index("idx_affairs_repair_lease", "t_affairs_repair_job", ["tenant_id", "state", "lease_until"])


def downgrade() -> None:
    if inspect(op.get_bind()).has_table("t_affairs_repair_job"):
        op.drop_table("t_affairs_repair_job")
