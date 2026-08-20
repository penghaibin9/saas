"""Add direct TeachingTask -> ProgramCourse provenance.

Revision ID: 20260818_acad_int_task_pc_prov
Revises: 20260817_acad_int_program_series

Historical tasks deliberately remain NULL.  The canonical generator writes the exact
ProgramCourse id for future tasks; this migration performs no semantic backfill.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260818_acad_int_task_pc_prov"
down_revision = "20260817_acad_int_program_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_aa_teaching_task",
        sa.Column(
            "source_program_course_id",
            sa.BigInteger(),
            nullable=True,
            comment="Exact t_aa_program_course.id used by canonical generation; legacy unresolved stays NULL",
        ),
    )


def downgrade() -> None:
    op.drop_column("t_aa_teaching_task", "source_program_course_id")
