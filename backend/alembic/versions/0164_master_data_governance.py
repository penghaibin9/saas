"""SYS-17：主数据责任与数据质量（数据域/责任人/规则/问题/合并留痕）。

Revision ID: 0164_master_data_governance
Revises: 0163_role_assignment_validity
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0164_master_data_governance"
down_revision = "0163_role_assignment_validity"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0164_master_data_governance requires MySQL")


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

    if not insp.has_table("t_data_domain"):
        op.create_table(
            "t_data_domain",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("domain_name", sa.String(128), nullable=False),
            sa.Column("owner_module", sa.String(64), nullable=False),
            sa.Column("authoritative_table", sa.String(128), nullable=False),
            sa.Column("description", sa.String(500)),
            sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_data_domain_tenant_id", "t_data_domain", ["tenant_id"])
        op.create_unique_constraint("uk_data_domain_code", "t_data_domain",
                                    ["tenant_id", "domain_code"])
        op.create_index("idx_data_domain_module", "t_data_domain", ["tenant_id", "owner_module"])

    if not insp.has_table("t_data_owner"):
        op.create_table(
            "t_data_owner",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
            sa.Column("owner_role_code", sa.String(64)),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_data_owner_tenant_id", "t_data_owner", ["tenant_id"])
        op.create_unique_constraint("uk_data_owner", "t_data_owner",
                                    ["tenant_id", "domain_code", "owner_user_id"])
        op.create_index("idx_data_owner_domain", "t_data_owner",
                        ["tenant_id", "domain_code", "status"])

    if not insp.has_table("t_data_quality_rule"):
        op.create_table(
            "t_data_quality_rule",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("rule_code", sa.String(64), nullable=False),
            sa.Column("rule_name", sa.String(128), nullable=False),
            sa.Column("rule_type", sa.String(24), nullable=False),
            sa.Column("severity", sa.String(8), nullable=False, server_default="P2"),
            sa.Column("executor_key", sa.String(64), nullable=False),
            sa.Column("sla_hours", sa.Integer()),
            sa.Column("params_json", sa.JSON()),
            sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_data_quality_rule_tenant_id", "t_data_quality_rule", ["tenant_id"])
        op.create_unique_constraint("uk_data_quality_rule_code", "t_data_quality_rule",
                                    ["tenant_id", "rule_code"])
        op.create_index("idx_data_quality_rule_domain", "t_data_quality_rule",
                        ["tenant_id", "domain_code", "status"])

    if not insp.has_table("t_data_quality_issue"):
        op.create_table(
            "t_data_quality_issue",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("rule_code", sa.String(64), nullable=False),
            sa.Column("issue_key", sa.String(255), nullable=False),
            sa.Column("severity", sa.String(8), nullable=False, server_default="P2"),
            sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
            sa.Column("object_type", sa.String(64)),
            sa.Column("object_id", sa.String(64)),
            sa.Column("summary", sa.String(500), nullable=False),
            sa.Column("evidence_json", sa.JSON()),
            sa.Column("owner_user_id", sa.BigInteger()),
            sa.Column("due_at", sa.DateTime()),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("assigned_at", sa.DateTime()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("resolved_by", sa.BigInteger()),
            sa.Column("resolve_note", sa.Text()),
            sa.Column("verified_at", sa.DateTime()),
            sa.Column("verified_by", sa.BigInteger()),
            sa.Column("verify_result", sa.String(24)),
            sa.Column("exception_until", sa.DateTime()),
            sa.Column("exception_reason", sa.String(500)),
            sa.Column("exception_approved_by", sa.BigInteger()),
            sa.Column("scan_batch_no", sa.String(64)),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_data_quality_issue_tenant_id", "t_data_quality_issue", ["tenant_id"])
        op.create_unique_constraint("uk_data_quality_issue_key", "t_data_quality_issue",
                                    ["tenant_id", "issue_key"])
        op.create_index("idx_data_quality_issue_status", "t_data_quality_issue",
                        ["tenant_id", "status", "severity"])
        op.create_index("idx_data_quality_issue_domain", "t_data_quality_issue",
                        ["tenant_id", "domain_code", "rule_code"])
        op.create_index("idx_data_quality_issue_due", "t_data_quality_issue",
                        ["tenant_id", "due_at"])

    if not insp.has_table("t_master_merge_event"):
        op.create_table(
            "t_master_merge_event",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("primary_object_id", sa.String(64), nullable=False),
            sa.Column("merged_object_id", sa.String(64), nullable=False),
            sa.Column("preview_hash", sa.String(64), nullable=False),
            sa.Column("references_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="PREVIEW"),
            sa.Column("reason", sa.String(500)),
            sa.Column("decided_at", sa.DateTime()),
            sa.Column("decided_by", sa.BigInteger()),
            *_common(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_master_merge_event_tenant_id", "t_master_merge_event", ["tenant_id"])
        op.create_index("idx_master_merge_domain", "t_master_merge_event",
                        ["tenant_id", "domain_code", "status"])
        op.create_index("idx_master_merge_objects", "t_master_merge_event",
                        ["tenant_id", "primary_object_id", "merged_object_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table in ("t_master_merge_event", "t_data_quality_issue", "t_data_quality_rule",
                  "t_data_owner", "t_data_domain"):
        if insp.has_table(table):
            op.drop_table(table)
