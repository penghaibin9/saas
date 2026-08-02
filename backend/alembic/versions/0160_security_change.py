"""SYS-09：安全变更集、变更项与激活流水。

草稿/审核/排期期间不写任何目标表，只有激活才在单事务内应用。
uk_security_revision 保证并发激活时只有一个能拿到下一个版本号。

Revision ID: 0160_security_change
Revises: 0159_scope_policy
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0160_security_change"
down_revision = "0159_scope_policy"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0160_security_change requires MySQL")


def _common_columns() -> list:
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

    if not insp.has_table("t_security_change_set"):
        op.create_table(
            "t_security_change_set",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("change_code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
            sa.Column("risk_level", sa.String(16), nullable=False, server_default="NORMAL"),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("impact_json", sa.JSON()),
            sa.Column("scheduled_at", sa.DateTime()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("activated_at", sa.DateTime()),
            sa.Column("rolled_back_at", sa.DateTime()),
            sa.Column("created_by_user", sa.BigInteger()),
            sa.Column("reviewed_by_user", sa.BigInteger()),
            sa.Column("activated_by_user", sa.BigInteger()),
            sa.Column("review_note", sa.String(1000)),
            sa.Column("self_review_ack", sa.String(200)),
            sa.Column("activated_revision", sa.Integer()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_security_change_set_tenant_id", "t_security_change_set", ["tenant_id"])
        op.create_index("ix_t_security_change_set_status", "t_security_change_set", ["status"])
        op.create_unique_constraint(
            "uk_security_change_code", "t_security_change_set", ["tenant_id", "change_code"]
        )
        op.create_index(
            "idx_security_change_status_schedule",
            "t_security_change_set",
            ["tenant_id", "status", "scheduled_at"],
        )

    if not insp.has_table("t_security_change_item"):
        op.create_table(
            "t_security_change_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("change_set_id", sa.BigInteger(), nullable=False),
            sa.Column("target_type", sa.String(32), nullable=False),
            sa.Column("target_id", sa.String(128), nullable=False),
            sa.Column("before_json", sa.JSON()),
            sa.Column("after_json", sa.JSON(), nullable=False),
            sa.Column("applied_at", sa.DateTime()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_security_change_item_tenant_id", "t_security_change_item", ["tenant_id"])
        op.create_index(
            "ix_t_security_change_item_change_set_id", "t_security_change_item", ["change_set_id"]
        )
        op.create_index("idx_security_item_set", "t_security_change_item", ["tenant_id", "change_set_id"])
        op.create_index(
            "idx_security_item_target", "t_security_change_item", ["tenant_id", "target_type", "target_id"]
        )

    if not insp.has_table("t_security_activation"):
        op.create_table(
            "t_security_activation",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("change_set_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.String(24), nullable=False),
            sa.Column("snapshot_json", sa.JSON(), nullable=False),
            sa.Column("actor_user_id", sa.BigInteger()),
            sa.Column("trace_id", sa.String(64)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_security_activation_tenant_id", "t_security_activation", ["tenant_id"])
        op.create_index("ix_t_security_activation_change_set_id", "t_security_activation", ["change_set_id"])
        op.create_index("ix_t_security_activation_trace_id", "t_security_activation", ["trace_id"])
        # 并发激活由这条唯一约束兜底：同一租户同一 revision 只能有一行
        op.create_unique_constraint("uk_security_revision", "t_security_activation", ["tenant_id", "revision"])
        op.create_index("idx_security_activation_time", "t_security_activation", ["tenant_id", "created_at"])


def downgrade() -> None:
    for table in ("t_security_activation", "t_security_change_item", "t_security_change_set"):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
