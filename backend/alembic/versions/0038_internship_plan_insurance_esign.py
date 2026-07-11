"""岗位实习 · 实习计划书 + 保险核验 + 协议电子签

Revision ID: 0038_internship_plan_insurance_esign
Revises: 0037_internship_process_report_change_eval
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0038_internship_plan_insurance_esign"
down_revision = "0037_internship_process_report_change_eval"
branch_labels = None
depends_on = None


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def _cols(bind, t):
    return {c["name"] for c in inspect(bind).get_columns(t)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_batch_plan"):
        op.create_table(
            "t_internship_batch_plan",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("objectives", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("tasks_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("published_by_name", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", name="uk_intern_batch_plan"),
        )
    if not _has(bind, "t_internship_plan_ack"):
        op.create_table(
            "t_internship_plan_ack",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("plan_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "internship_id", "plan_id", name="uk_intern_plan_ack"),
        )
    if not _has(bind, "t_internship_insurance"):
        op.create_table(
            "t_internship_insurance",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("policy_no", sa.String(100), nullable=True),
            sa.Column("insurer_name", sa.String(200), nullable=True),
            sa.Column("coverage_type", sa.String(100), nullable=True),
            sa.Column("effective_date", sa.String(10), nullable=True),
            sa.Column("expiry_date", sa.String(10), nullable=True),
            sa.Column("file_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="NOT_SUBMITTED"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("verify_comment", sa.String(500), nullable=True),
            sa.Column("verified_by_name", sa.String(50), nullable=True),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "internship_id", name="uk_intern_insurance"),
        )
    if _has(bind, "t_internship_agreement"):
        cols = _cols(bind, "t_internship_agreement")
        for name, col in [
            ("esign_provider", sa.Column("esign_provider", sa.String(30), nullable=False, server_default="INTERNAL")),
            ("esign_initiated_at", sa.Column("esign_initiated_at", sa.DateTime(), nullable=True)),
            ("esign_initiated_by", sa.Column("esign_initiated_by", sa.String(50), nullable=True)),
            ("esign_student_at", sa.Column("esign_student_at", sa.DateTime(), nullable=True)),
            ("esign_enterprise_at", sa.Column("esign_enterprise_at", sa.DateTime(), nullable=True)),
            ("esign_school_at", sa.Column("esign_school_at", sa.DateTime(), nullable=True)),
        ]:
            if name not in cols:
                op.add_column("t_internship_agreement", col)


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_agreement"):
        for name in ("esign_school_at", "esign_enterprise_at", "esign_student_at",
                     "esign_initiated_by", "esign_initiated_at", "esign_provider"):
            if name in _cols(bind, "t_internship_agreement"):
                op.drop_column("t_internship_agreement", name)
    for t in ("t_internship_insurance", "t_internship_plan_ack", "t_internship_batch_plan"):
        if _has(bind, t):
            op.drop_table(t)
