"""岗位实习 · 计划任务完成度

Revision ID: 0041_internship_plan_task_progress
Revises: 0040_internship_0037_created_by
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0041_internship_plan_task_progress"
down_revision = "0040_internship_0037_created_by"
branch_labels = None
depends_on = None


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, "t_internship_plan_task_progress"):
        op.create_table(
            "t_internship_plan_task_progress",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("plan_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("internship_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("task_sort_order", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="NOT_STARTED"),
            sa.Column("student_note", sa.String(500), nullable=True),
            sa.Column("evidence_file_id", sa.String(64), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by_name", sa.String(50), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "internship_id", "plan_id", "task_sort_order",
                                name="uk_intern_plan_task_prog"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_plan_task_progress"):
        op.drop_table("t_internship_plan_task_progress")
