"""SYS-14：流程节点动作安全策略与版本变更迁移事件。

Revision ID: 0165_workflow_security_policy
Revises: 0164_master_data_governance
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0165_workflow_security_policy"
down_revision = "0164_master_data_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0165_workflow_security_policy requires MySQL")


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

    if not insp.has_table("t_workflow_action_policy"):
        op.create_table(
            "t_workflow_action_policy",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("workflow_code", sa.String(100), nullable=False),
            sa.Column("node_code", sa.String(100), nullable=False, server_default=""),
            sa.Column("policy_type", sa.String(24), nullable=False, server_default="NODE_ACTION"),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("action_permission_code", sa.String(160)),
            sa.Column("version_strategy", sa.String(16), nullable=False, server_default="DYNAMIC"),
            sa.Column("reason", sa.String(500)),
            sa.Column("submitted_by", sa.BigInteger()),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("reviewed_by", sa.BigInteger()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("retired_by", sa.BigInteger()),
            sa.Column("retired_at", sa.DateTime()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_workflow_action_policy_tenant_id",
                        "t_workflow_action_policy", ["tenant_id"])
        op.create_index("ix_t_workflow_action_policy_workflow_code",
                        "t_workflow_action_policy", ["workflow_code"])
        op.create_unique_constraint("uk_workflow_action_policy_scope",
                                    "t_workflow_action_policy",
                                    ["tenant_id", "workflow_code", "node_code", "policy_type"])
        op.create_index("idx_workflow_action_policy_lookup", "t_workflow_action_policy",
                        ["tenant_id", "workflow_code", "status"])

    if not insp.has_table("t_workflow_version_migration_event"):
        op.create_table(
            "t_workflow_version_migration_event",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("workflow_code", sa.String(100), nullable=False),
            sa.Column("from_definition_version", sa.String(30)),
            sa.Column("to_definition_version", sa.String(30)),
            sa.Column("affected_instance_count", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("affected_instance_ids_json", sa.JSON()),
            sa.Column("reason", sa.String(500)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_workflow_version_migration_event_tenant_id",
                        "t_workflow_version_migration_event", ["tenant_id"])
        op.create_index("idx_workflow_version_migration_lookup",
                        "t_workflow_version_migration_event",
                        ["tenant_id", "workflow_code", "created_at"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_workflow_version_migration_event", "t_workflow_action_policy"):
        if insp.has_table(table):
            op.drop_table(table)
