"""Academic C W4: real GradeTask deadline/extension truth.

Revision ID: 20260818_aa_grade_deadline
Revises: 20260814_merge_ix_v93_main

This is an additive C-line revision. PR #148 was cut from the published
20260814_merge_ix_v93_main head. Current main has since advanced on another
Alembic lineage (including #145); final integration must merge the two heads
rather than rewrite either published ancestry.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260818_aa_grade_deadline"
down_revision = "20260814_merge_ix_v93_main"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260818_aa_grade_deadline requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {row["name"] for row in insp.get_columns("t_aa_grade_task")}
    if "deadline_at" not in columns:
        op.add_column("t_aa_grade_task", sa.Column("deadline_at", sa.DateTime(), nullable=True))
    if "deadline_updated_at" not in columns:
        op.add_column("t_aa_grade_task", sa.Column("deadline_updated_at", sa.DateTime(), nullable=True))
    indexes = {row["name"] for row in inspect(bind).get_indexes("t_aa_grade_task")}
    if "ix_aa_grade_task_deadline" not in indexes:
        op.create_index(
            "ix_aa_grade_task_deadline",
            "t_aa_grade_task",
            ["tenant_id", "status", "deadline_at"],
            unique=False,
        )


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = {row["name"] for row in insp.get_indexes("t_aa_grade_task")}
    if "ix_aa_grade_task_deadline" in indexes:
        op.drop_index("ix_aa_grade_task_deadline", table_name="t_aa_grade_task")
    columns = {row["name"] for row in inspect(bind).get_columns("t_aa_grade_task")}
    if "deadline_updated_at" in columns:
        op.drop_column("t_aa_grade_task", "deadline_updated_at")
    if "deadline_at" in columns:
        op.drop_column("t_aa_grade_task", "deadline_at")
