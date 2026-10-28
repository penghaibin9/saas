"""Yiyang C05/G12-G13 structured rotation and payroll facts.

Revision ID: ix0006
Revises: ix0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0006"
down_revision = "ix0005"
branch_labels = None
depends_on = None


def _common():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    op.create_table(
        "t_internship_rotation",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("rotation_seq", sa.Integer(), nullable=False),
        sa.Column("department_name", sa.String(160), nullable=False),
        sa.Column("department_manager_name", sa.String(100), nullable=True),
        sa.Column("mentor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("mentor_name", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PLANNED'")),
        sa.Column("student_self_evaluation", sa.Text(), nullable=True),
        sa.Column("student_self_rating", sa.Integer(), nullable=True),
        sa.Column("self_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("theory_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("skill_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("mentor_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_rule_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("evaluator_name", sa.String(100), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("evaluation_comment", sa.String(1000), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "internship_id", "rotation_seq", name="uk_ix_rotation_seq"),
    )
    op.create_index("ix_ix_rotation_student", "t_internship_rotation", ["tenant_id", "student_id", "batch_id", "status", "is_deleted"])
    for col in ("tenant_id", "internship_id", "student_id", "batch_id", "mentor_user_id"):
        op.create_index(f"ix_t_internship_rotation_{col}", "t_internship_rotation", [col])

    op.create_table(
        "t_internship_rotation_project",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("rotation_id", sa.BigInteger(), nullable=False),
        sa.Column("project_seq", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(200), nullable=False),
        sa.Column("project_content", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PLANNED'")),
        sa.Column("mentor_note", sa.String(1000), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "rotation_id", "project_seq", name="uk_ix_rotation_project_seq"),
    )
    op.create_index("ix_ix_rotation_project_status", "t_internship_rotation_project", ["tenant_id", "rotation_id", "status", "is_deleted"])
    for col in ("tenant_id", "rotation_id"):
        op.create_index(f"ix_t_internship_rotation_project_{col}", "t_internship_rotation_project", [col])

    op.create_table(
        "t_internship_payroll_statement",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("pay_month", sa.String(7), nullable=False),
        sa.Column("agreed_salary_snapshot", sa.Numeric(12, 2), nullable=True),
        sa.Column("agreed_salary_currency", sa.String(8), nullable=False, server_default=sa.text("'CNY'")),
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_common(),
        sa.UniqueConstraint("tenant_id", "internship_id", "pay_month", name="uk_ix_payroll_month"),
    )
    op.create_index("ix_ix_payroll_student", "t_internship_payroll_statement", ["tenant_id", "student_id", "batch_id", "pay_month", "is_deleted"])
    for col in ("tenant_id", "internship_id", "student_id", "batch_id", "current_version_id"):
        op.create_index(f"ix_t_internship_payroll_statement_{col}", "t_internship_payroll_statement", [col])

    op.create_table(
        "t_internship_payroll_version",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("statement_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("actual_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default=sa.text("'CNY'")),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("evidence_file_id", sa.BigInteger(), nullable=True),
        sa.Column("evidence_sha256", sa.String(64), nullable=True),
        sa.Column("submit_note", sa.String(500), nullable=True),
        sa.Column("correction_reason", sa.String(500), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'SUBMITTED'")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_name", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        *_common(),
        sa.UniqueConstraint("tenant_id", "statement_id", "revision_no", name="uk_ix_payroll_revision"),
    )
    op.create_index("ix_ix_payroll_current", "t_internship_payroll_version", ["tenant_id", "statement_id", "is_current", "status", "is_deleted"])
    for col in ("tenant_id", "statement_id", "evidence_file_id"):
        op.create_index(f"ix_t_internship_payroll_version_{col}", "t_internship_payroll_version", [col])


def downgrade() -> None:
    op.drop_table("t_internship_payroll_version")
    op.drop_table("t_internship_payroll_statement")
    op.drop_table("t_internship_rotation_project")
    op.drop_table("t_internship_rotation")
