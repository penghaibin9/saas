"""Academic C W4: real GradeTask deadline/extension truth.

Revision ID: 20260818_aa_grade_deadline
Revises: 20260814_merge_ix_v93_main

This is an additive C-line revision. PR #148 was cut from the published
20260814_merge_ix_v93_main head. Current main has since advanced on another
Alembic lineage (including #145); final integration merges the two heads rather
than rewriting either published ancestry.

The application performs a friendly deadline preflight, while a MySQL BEFORE UPDATE
trigger is the final atomic guard against a submit crossing the deadline between
preflight and the canonical status mutation.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260818_aa_grade_deadline"
down_revision = "20260814_merge_ix_v93_main"
branch_labels = None
depends_on = None

_TRIGGER = "trg_aa_grade_task_deadline_submit_guard"


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

    # App preflight and canonical submit live in separate service transactions today.
    # The trigger closes that tiny TOCTOU window at the authoritative status mutation.
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER}")
    op.execute(
        f"""
        CREATE TRIGGER {_TRIGGER}
        BEFORE UPDATE ON t_aa_grade_task
        FOR EACH ROW
        BEGIN
            IF NEW.status = 'SUBMITTED'
               AND OLD.status IN ('INPUTTING', 'RETURNED')
               AND OLD.deadline_at IS NOT NULL
               AND UTC_TIMESTAMP() > OLD.deadline_at THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'GRADE_DEADLINE_EXPIRED';
            END IF;
        END
        """
    )


def downgrade() -> None:
    _require_mysql()
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER}")
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
