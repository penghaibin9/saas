"""SYS-08：组织安全树的显式 DENY、精细 ALLOW 与未来生效。

不动 t_data_scope_rule：既有"角色 → 范围类型"和 data_scope_service 里的 provider 继续
真实参与鉴权。本迁移只补上今天无法表达的东西——显式 DENY、敏感专项和未来生效。

Revision ID: 0159_scope_policy
Revises: 0158_permission_governance
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0159_scope_policy"
down_revision = "0158_permission_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0159_scope_policy requires MySQL")


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

    if not insp.has_table("t_scope_policy_target"):
        op.create_table(
            "t_scope_policy_target",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("effect", sa.String(8), nullable=False, server_default="ALLOW"),
            sa.Column("target_type", sa.String(24), nullable=False),
            sa.Column("target_id", sa.String(128), nullable=False),
            sa.Column("include_children", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            sa.Column("reason", sa.String(1000)),
            sa.Column("sensitive_domain", sa.String(64)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_scope_policy_target_tenant_id", "t_scope_policy_target", ["tenant_id"])
        op.create_index("ix_t_scope_policy_target_role_code", "t_scope_policy_target", ["role_code"])
        op.create_index("ix_t_scope_policy_target_status", "t_scope_policy_target", ["status"])
        op.create_unique_constraint(
            "uk_scope_policy_target",
            "t_scope_policy_target",
            ["tenant_id", "role_code", "effect", "target_type", "target_id", "effective_at"],
        )
        op.create_index(
            "idx_scope_policy_role_effect", "t_scope_policy_target", ["tenant_id", "role_code", "effect", "status"]
        )
        op.create_index(
            "idx_scope_policy_target", "t_scope_policy_target", ["tenant_id", "target_type", "target_id", "status"]
        )

    if not insp.has_table("t_scope_policy_decision_log"):
        op.create_table(
            "t_scope_policy_decision_log",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(24), nullable=False),
            sa.Column("target_id", sa.String(128), nullable=False),
            sa.Column("decision", sa.String(8), nullable=False),
            sa.Column("reason_code", sa.String(64), nullable=False),
            sa.Column("detail_json", sa.JSON()),
            sa.Column("trace_id", sa.String(64)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_scope_policy_decision_log_tenant_id", "t_scope_policy_decision_log", ["tenant_id"])
        op.create_index("ix_t_scope_policy_decision_log_trace_id", "t_scope_policy_decision_log", ["trace_id"])
        op.create_index(
            "idx_scope_decision_role_time", "t_scope_policy_decision_log", ["tenant_id", "role_code", "created_at"]
        )


def downgrade() -> None:
    for table in ("t_scope_policy_decision_log", "t_scope_policy_target"):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
