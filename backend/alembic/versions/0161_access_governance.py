"""SYS-10：访问决策留痕、权限复核、职责分离与紧急访问。

Revision ID: 0161_access_governance
Revises: 0160_security_change
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0161_access_governance"
down_revision = "0160_security_change"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0161_access_governance requires MySQL")


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

    if not insp.has_table("t_access_decision_trace"):
        op.create_table(
            "t_access_decision_trace",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("trace_id", sa.String(64), nullable=False),
            sa.Column("subject_user_id", sa.BigInteger()),
            sa.Column("active_role_code", sa.String(64)),
            sa.Column("action_code", sa.String(160), nullable=False),
            sa.Column("resource_type", sa.String(64)),
            sa.Column("resource_id_hash", sa.String(128)),
            sa.Column("decision", sa.String(8), nullable=False),
            sa.Column("reason_code", sa.String(64), nullable=False),
            sa.Column("security_revision", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("decision_json", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_access_decision_trace_tenant_id", "t_access_decision_trace", ["tenant_id"])
        op.create_unique_constraint("uk_access_trace", "t_access_decision_trace", ["tenant_id", "trace_id"])
        op.create_index(
            "idx_access_subject_time", "t_access_decision_trace", ["tenant_id", "subject_user_id", "created_at"]
        )
        op.create_index(
            "idx_access_decision_reason",
            "t_access_decision_trace",
            ["tenant_id", "decision", "reason_code", "created_at"],
        )

    if not insp.has_table("t_access_review_campaign"):
        op.create_table(
            "t_access_review_campaign",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_code", sa.String(64), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("scope_json", sa.JSON()),
            sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
            sa.Column("due_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_access_review_campaign_tenant_id", "t_access_review_campaign", ["tenant_id"])
        op.create_index("ix_t_access_review_campaign_status", "t_access_review_campaign", ["status"])
        op.create_unique_constraint(
            "uk_review_campaign_code", "t_access_review_campaign", ["tenant_id", "campaign_code"]
        )
        op.create_index(
            "idx_review_campaign_status", "t_access_review_campaign", ["tenant_id", "status", "due_at"]
        )

    if not insp.has_table("t_access_review_item"):
        op.create_table(
            "t_access_review_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("campaign_id", sa.BigInteger(), nullable=False),
            sa.Column("subject_user_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("decision", sa.String(24)),
            sa.Column("decided_by", sa.BigInteger()),
            sa.Column("decided_at", sa.DateTime()),
            sa.Column("note", sa.String(1000)),
            sa.Column("follow_up_change_set_id", sa.BigInteger()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_access_review_item_tenant_id", "t_access_review_item", ["tenant_id"])
        op.create_index("ix_t_access_review_item_campaign_id", "t_access_review_item", ["campaign_id"])
        op.create_unique_constraint(
            "uk_review_item",
            "t_access_review_item",
            ["tenant_id", "campaign_id", "subject_user_id", "role_code"],
        )
        op.create_index(
            "idx_review_item_pending", "t_access_review_item", ["tenant_id", "campaign_id", "decision"]
        )

    if not insp.has_table("t_sod_rule"):
        op.create_table(
            "t_sod_rule",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("rule_code", sa.String(64), nullable=False),
            sa.Column("role_a", sa.String(64), nullable=False),
            sa.Column("role_b", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False, server_default="HIGH"),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_sod_rule_tenant_id", "t_sod_rule", ["tenant_id"])
        op.create_index("ix_t_sod_rule_status", "t_sod_rule", ["status"])
        op.create_unique_constraint("uk_sod_rule_code", "t_sod_rule", ["tenant_id", "rule_code"])
        op.create_index("idx_sod_rule_roles", "t_sod_rule", ["tenant_id", "role_a", "role_b", "status"])

    if not insp.has_table("t_sod_violation"):
        op.create_table(
            "t_sod_violation",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("rule_code", sa.String(64), nullable=False),
            sa.Column("subject_user_id", sa.BigInteger(), nullable=False),
            sa.Column("detected_roles_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
            sa.Column("resolution", sa.String(1000)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_sod_violation_tenant_id", "t_sod_violation", ["tenant_id"])
        op.create_index("ix_t_sod_violation_subject_user_id", "t_sod_violation", ["subject_user_id"])
        op.create_index("ix_t_sod_violation_status", "t_sod_violation", ["status"])
        op.create_unique_constraint(
            "uk_sod_violation", "t_sod_violation", ["tenant_id", "rule_code", "subject_user_id"]
        )
        op.create_index("idx_sod_violation_status", "t_sod_violation", ["tenant_id", "status"])

    if not insp.has_table("t_emergency_access_session"):
        op.create_table(
            "t_emergency_access_session",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("session_code", sa.String(64), nullable=False),
            sa.Column("subject_user_id", sa.BigInteger(), nullable=False),
            sa.Column("granted_role_code", sa.String(64), nullable=False),
            sa.Column("ticket_ref", sa.String(200), nullable=False),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_emergency_access_session_tenant_id", "t_emergency_access_session", ["tenant_id"])
        op.create_index(
            "ix_t_emergency_access_session_subject_user_id", "t_emergency_access_session", ["subject_user_id"]
        )
        op.create_index("ix_t_emergency_access_session_status", "t_emergency_access_session", ["status"])
        op.create_unique_constraint(
            "uk_emergency_session_code", "t_emergency_access_session", ["tenant_id", "session_code"]
        )
        op.create_index(
            "idx_emergency_active",
            "t_emergency_access_session",
            ["tenant_id", "subject_user_id", "status", "expires_at"],
        )


def downgrade() -> None:
    for table in (
        "t_emergency_access_session",
        "t_sod_violation",
        "t_sod_rule",
        "t_access_review_item",
        "t_access_review_campaign",
        "t_access_decision_trace",
    ):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
