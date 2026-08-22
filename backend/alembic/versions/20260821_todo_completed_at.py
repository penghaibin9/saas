"""TP-W02: give UnifiedTodo a real completed_at fact, independent from updated_at.

updated_at bumps on any edit (remark, reassignment, ...); doneToday counted off it would
wrongly include today's edits of historical DONE rows. completed_at is only stamped by the
before_flush listener in app/models/approval.py on a genuine PENDING/CANCELLED -> DONE
transition (and cleared on DONE -> non-DONE), so it is a true completion timestamp.

Revision ID: 20260821_todo_completed_at
Revises: 20260820_teacher_emp_reco
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260821_todo_completed_at"
down_revision = "20260820_teacher_emp_reco"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_unified_todo", sa.Column("completed_at", sa.DateTime(), nullable=True))
    # Backfill existing DONE rows with updated_at so historical doneToday-adjacent queries
    # do not go from "some value" to "all NULL" on the day of deploy; this is a one-time best
    # effort snapshot, not a claim that updated_at was ever an accurate completion time.
    op.execute(
        "UPDATE t_unified_todo SET completed_at = updated_at WHERE status = 'DONE' AND completed_at IS NULL"
    )
    op.create_index(
        "ix_todo_tenant_completed_at", "t_unified_todo", ["tenant_id", "completed_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_todo_tenant_completed_at", table_name="t_unified_todo")
    op.drop_column("t_unified_todo", "completed_at")
