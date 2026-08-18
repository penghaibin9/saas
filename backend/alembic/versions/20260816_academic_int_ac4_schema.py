"""Academic INT A-C4 shared authority schema.

Revision ID: 20260816_acad_int_ac4
Revises: 20260816_internship_e_m8

Additive and deliberately non-guessing:
- legacy ProgramCourse and TeachingTask formation remain NULL unless explicit provenance exists;
- existing TeachingTaskBatch rows keep editable_scope_key NULL until explicit reconciliation;
- MySQL UNIQUE NULL semantics preserve history while future live writers reserve one scope.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_acad_int_ac4"
down_revision = "20260816_internship_e_m8"
branch_labels = None
depends_on = None

FORMATION_CHECK = "formation_mode IS NULL OR formation_mode IN ('ADMIN_FIXED','SELECTABLE','MERGED','RETAKE','LAYERED')"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260816_acad_int_ac4 requires MySQL")


def upgrade() -> None:
    _require_mysql()
    op.add_column(
        "t_aa_program_course",
        sa.Column(
            "formation_mode", sa.String(length=20), nullable=True,
            comment="ADMIN_FIXED/SELECTABLE/MERGED/RETAKE/LAYERED; unresolved legacy stays NULL",
        ),
    )
    op.create_check_constraint(
        "ck_aa_program_course_formation_mode",
        "t_aa_program_course",
        FORMATION_CHECK,
    )

    op.add_column(
        "t_aa_teaching_task_batch",
        sa.Column(
            "editable_scope_key", sa.String(length=64), nullable=True,
            comment="INT A-C4 live editable scope key; history/non-editable rows stay NULL",
        ),
    )
    op.create_unique_constraint(
        "uk_aa_task_batch_editable_scope",
        "t_aa_teaching_task_batch",
        ["tenant_id", "editable_scope_key"],
    )

    op.add_column(
        "t_aa_teaching_task",
        sa.Column(
            "formation_mode", sa.String(length=20), nullable=True,
            comment="ADMIN_FIXED/SELECTABLE/MERGED/RETAKE/LAYERED; unresolved legacy stays NULL",
        ),
    )
    op.create_check_constraint(
        "ck_aa_teaching_task_formation_mode",
        "t_aa_teaching_task",
        FORMATION_CHECK,
    )


def downgrade() -> None:
    _require_mysql()
    op.drop_constraint(
        "ck_aa_teaching_task_formation_mode",
        "t_aa_teaching_task",
        type_="check",
    )
    op.drop_column("t_aa_teaching_task", "formation_mode")
    op.drop_constraint(
        "uk_aa_task_batch_editable_scope",
        "t_aa_teaching_task_batch",
        type_="unique",
    )
    op.drop_column("t_aa_teaching_task_batch", "editable_scope_key")
    op.drop_constraint(
        "ck_aa_program_course_formation_mode",
        "t_aa_program_course",
        type_="check",
    )
    op.drop_column("t_aa_program_course", "formation_mode")
