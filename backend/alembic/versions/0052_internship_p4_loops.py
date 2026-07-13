"""Internship P4 business loops: enterprise communication / visit plan / complaint.

07 整改方案 §5 三个业务闭环建表。

Revision ID: 0052_internship_p4_loops
Revises: 0051_gd_core_table_baseline
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0052_internship_p4_loops"
down_revision = "0051_gd_core_table_baseline"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def _common():
    return [
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def _idx(table: str, cols) -> None:
    for c in cols:
        op.create_index(f"ix_{table}_{c}", table, [c])


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_internship_communication_log"):
        op.create_table(
            "t_internship_communication_log",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("enterprise_id", sa.BigInteger(), nullable=False),
            sa.Column("internship_id", sa.BigInteger(), nullable=True),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("position_id", sa.BigInteger(), nullable=True),
            sa.Column("communication_type", sa.String(20), nullable=False, server_default="PHONE"),
            sa.Column("direction", sa.String(20), nullable=False, server_default="SCHOOL"),
            sa.Column("contact_id", sa.BigInteger(), nullable=True),
            sa.Column("contact_name_snapshot", sa.String(50), nullable=True),
            sa.Column("advisor_name", sa.String(50), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("result", sa.String(1000), nullable=True),
            sa.Column("follow_up_required", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("follow_up_due_at", sa.DateTime(), nullable=True),
            sa.Column("follow_up_owner_id", sa.BigInteger(), nullable=True),
            sa.Column("follow_up_done", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("file_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="NORMAL"),
            *_common(),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        _idx("t_internship_communication_log",
             ("tenant_id", "enterprise_id", "internship_id", "student_id", "status"))

    if not _has(bind, "t_internship_visit_plan"):
        op.create_table(
            "t_internship_visit_plan",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("college_id", sa.BigInteger(), nullable=True),
            sa.Column("enterprise_id", sa.BigInteger(), nullable=True),
            sa.Column("enterprise_name", sa.String(200), nullable=True),
            sa.Column("owner_name", sa.String(50), nullable=True),
            sa.Column("collaborators", sa.String(500), nullable=True),
            sa.Column("student_scope", sa.Text(), nullable=True),
            sa.Column("plan_date", sa.String(10), nullable=True),
            sa.Column("time_window", sa.String(50), nullable=True),
            sa.Column("method", sa.String(20), nullable=False, server_default="ONSITE"),
            sa.Column("location", sa.String(200), nullable=True),
            sa.Column("objective", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("plan_type", sa.String(20), nullable=False, server_default="VISIT"),
            sa.Column("remind_at", sa.DateTime(), nullable=True),
            sa.Column("visit_id", sa.BigInteger(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("cancel_reason", sa.String(500), nullable=True),
            *_common(),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        _idx("t_internship_visit_plan",
             ("tenant_id", "batch_id", "college_id", "enterprise_id", "status"))

    if not _has(bind, "t_internship_complaint"):
        op.create_table(
            "t_internship_complaint",
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("complaint_no", sa.String(40), nullable=True),
            sa.Column("source", sa.String(20), nullable=False, server_default="STUDENT"),
            sa.Column("target_type", sa.String(20), nullable=True),
            sa.Column("enterprise_id", sa.BigInteger(), nullable=True),
            sa.Column("position_id", sa.BigInteger(), nullable=True),
            sa.Column("student_id", sa.BigInteger(), nullable=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=True),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("evidence_file_id", sa.String(64), nullable=True),
            sa.Column("complainant_contact_encrypted", sa.String(200), nullable=True),
            sa.Column("confidential_level", sa.String(20), nullable=False, server_default="NORMAL"),
            sa.Column("status", sa.String(20), nullable=False, server_default="RECEIVED"),
            sa.Column("accepted_by_name", sa.String(50), nullable=True),
            sa.Column("owner_name", sa.String(50), nullable=True),
            sa.Column("accept_deadline", sa.String(10), nullable=True),
            sa.Column("resolve_deadline", sa.String(10), nullable=True),
            sa.Column("conclusion", sa.Text(), nullable=True),
            sa.Column("followup_result", sa.Text(), nullable=True),
            sa.Column("risk_id", sa.BigInteger(), nullable=True),
            *_common(),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        _idx("t_internship_complaint",
             ("tenant_id", "complaint_no", "enterprise_id", "student_id", "batch_id", "status", "risk_id"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("t_internship_complaint", "t_internship_visit_plan", "t_internship_communication_log"):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
