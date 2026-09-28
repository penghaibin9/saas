"""Yiyang C08/G16 teacher execution and emergency notices.

Revision ID: ix0009
Revises: ix0008
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0009"
down_revision = "ix0008"
branch_labels = None
depends_on = None


def _common_columns():
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
        "t_internship_teacher_checkin",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_name_snapshot", sa.String(100), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("checked_in_at", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("accuracy_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "local_date",
            name="uk_ix_teacher_checkin_day",
        ),
    )
    op.create_index(
        "ix_ix_teacher_checkin_batch_teacher",
        "t_internship_teacher_checkin",
        ["tenant_id", "batch_id", "teacher_user_id", "local_date"],
    )

    op.create_table(
        "t_internship_teacher_work_report",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("teacher_name_snapshot", sa.String(100), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("work_content", sa.Text(), nullable=False),
        sa.Column("issue_content", sa.Text(), nullable=True),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column("student_count", sa.Integer(), nullable=True),
        sa.Column("attachment_file_ids_json", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        *_common_columns(),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "teacher_user_id", "report_date",
            name="uk_ix_teacher_work_report_day",
        ),
    )
    op.create_index(
        "ix_ix_teacher_work_report_batch_teacher",
        "t_internship_teacher_work_report",
        ["tenant_id", "batch_id", "teacher_user_id", "report_date"],
    )

    op.create_table(
        "t_internship_emergency_notice",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sender_user_id", sa.BigInteger(), nullable=True),
        sa.Column("sender_name_snapshot", sa.String(100), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default="PUBLISHED"),
        sa.Column("outbox_id", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("withdraw_reason", sa.String(500), nullable=True),
        *_common_columns(),
    )
    op.create_index(
        "ix_ix_emergency_notice_batch_published",
        "t_internship_emergency_notice",
        ["tenant_id", "batch_id", "published_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_emergency_notice")
    op.drop_table("t_internship_teacher_work_report")
    op.drop_table("t_internship_teacher_checkin")
