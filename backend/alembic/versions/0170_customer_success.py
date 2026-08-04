"""PLAT-05：客户健康、工单、培训与续费。

Revision ID: 0170_customer_success
Revises: 0169_change_management
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0170_customer_success"
down_revision = "0169_change_management"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0170_customer_success requires MySQL")


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

    if not insp.has_table("t_support_ticket"):
        op.create_table(
            "t_support_ticket",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.String(2000)),
            sa.Column("severity", sa.String(10), nullable=False, server_default="P2"),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
            sa.Column("reporter_name", sa.String(100)),
            sa.Column("assignee_user_id", sa.BigInteger()),
            sa.Column("assignee_name", sa.String(100)),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("resolution_note", sa.String(2000)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_support_ticket_tenant", "t_support_ticket", ["tenant_id"])
        op.create_index("ix_t_support_ticket_status", "t_support_ticket", ["status"])

    if not insp.has_table("t_training_record"):
        op.create_table(
            "t_training_record",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("topic", sa.String(200), nullable=False),
            sa.Column("trainer_name", sa.String(100)),
            sa.Column("scheduled_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED"),
            sa.Column("attendee_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("note", sa.String(1000)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_training_record_tenant", "t_training_record", ["tenant_id"])
        op.create_index("ix_t_training_record_status", "t_training_record", ["status"])

    if not insp.has_table("t_renewal_task"):
        op.create_table(
            "t_renewal_task",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("due_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("owner_user_id", sa.BigInteger()),
            sa.Column("owner_name", sa.String(100)),
            sa.Column("note", sa.String(1000)),
            sa.Column("last_contacted_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_renewal_task_tenant", "t_renewal_task", ["tenant_id"])
        op.create_index("ix_t_renewal_task_status", "t_renewal_task", ["status"])
        op.create_index("ix_t_renewal_task_due_at", "t_renewal_task", ["due_at"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_renewal_task", "t_training_record", "t_support_ticket"):
        if insp.has_table(table):
            op.drop_table(table)
