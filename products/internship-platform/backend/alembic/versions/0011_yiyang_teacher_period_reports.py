"""Yiyang C08/G16 teacher weekly/monthly/summary facts.

Revision ID: ix0011
Revises: ix0010
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0011"
down_revision = "ix0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_teacher_period_report",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_name_snapshot", sa.String(100), nullable=False),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("period_key", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("issue_content", sa.Text(), nullable=True),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column("student_count", sa.Integer(), nullable=True),
        sa.Column("attachment_file_ids_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "report_type", "period_key",
            name="uk_ix_teacher_period_report",
        ),
    )
    op.create_index(
        "ix_ix_teacher_period_report_lookup",
        "t_internship_teacher_period_report",
        ["tenant_id", "batch_id", "teacher_user_id", "report_type", "period_key"],
    )
    op.create_index(
        "ix_t_internship_teacher_period_report_batch_id",
        "t_internship_teacher_period_report", ["batch_id"],
    )
    op.create_index(
        "ix_t_internship_teacher_period_report_teacher_user_id",
        "t_internship_teacher_period_report", ["teacher_user_id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_teacher_period_report")
