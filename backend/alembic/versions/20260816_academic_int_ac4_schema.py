"""Academic INT A-C4 shared authority schema.

Revision ID: 20260816_acad_int_ac4
Revises: 20260816_internship_e_m8

Additive and deliberately non-guessing:
- legacy ProgramCourse and TeachingTask formation remain NULL unless explicit provenance exists;
- existing TeachingTaskBatch rows keep editable_scope_key NULL until explicit reconciliation;
- MySQL UNIQUE NULL semantics preserve history while future live writers reserve one scope.

The ProgramCourse column is shared with A's nullable expand revision. This migration
is descendant-safe in either Alembic branch order: it creates the column when absent,
or tightens only its declared VARCHAR width before installing the INT CHECK contract.
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


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _check_names(table_name: str) -> set[str]:
    return {
        check.get("name")
        for check in sa.inspect(op.get_bind()).get_check_constraints(table_name)
        if check.get("name")
    }


def _unique_names(table_name: str) -> set[str]:
    return {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _revision_is_current(revision_id: str) -> bool:
    row = op.get_bind().execute(
        sa.text("SELECT 1 FROM alembic_version WHERE version_num = :revision_id"),
        {"revision_id": revision_id},
    ).first()
    return row is not None


def _ensure_formation_column(table_name: str) -> None:
    columns = _columns(table_name)
    current = columns.get("formation_mode")
    if current is None:
        op.add_column(
            table_name,
            sa.Column(
                "formation_mode",
                sa.String(length=20),
                nullable=True,
                comment="ADMIN_FIXED/SELECTABLE/MERGED/RETAKE/LAYERED; unresolved legacy stays NULL",
            ),
        )
        return

    current_length = getattr(current.get("type"), "length", None)
    if current_length != 20:
        op.alter_column(
            table_name,
            "formation_mode",
            existing_type=current["type"],
            type_=sa.String(length=20),
            existing_nullable=bool(current.get("nullable", True)),
            existing_comment=current.get("comment"),
        )


def upgrade() -> None:
    _require_mysql()

    _ensure_formation_column("t_aa_program_course")
    if "ck_aa_program_course_formation_mode" not in _check_names("t_aa_program_course"):
        op.create_check_constraint(
            "ck_aa_program_course_formation_mode",
            "t_aa_program_course",
            FORMATION_CHECK,
        )

    if "editable_scope_key" not in _columns("t_aa_teaching_task_batch"):
        op.add_column(
            "t_aa_teaching_task_batch",
            sa.Column(
                "editable_scope_key", sa.String(length=64), nullable=True,
                comment="INT A-C4 live editable scope key; history/non-editable rows stay NULL",
            ),
        )
    if "uk_aa_task_batch_editable_scope" not in _unique_names("t_aa_teaching_task_batch"):
        op.create_unique_constraint(
            "uk_aa_task_batch_editable_scope",
            "t_aa_teaching_task_batch",
            ["tenant_id", "editable_scope_key"],
        )

    _ensure_formation_column("t_aa_teaching_task")
    if "ck_aa_teaching_task_formation_mode" not in _check_names("t_aa_teaching_task"):
        op.create_check_constraint(
            "ck_aa_teaching_task_formation_mode",
            "t_aa_teaching_task",
            FORMATION_CHECK,
        )


def downgrade() -> None:
    _require_mysql()

    if "ck_aa_teaching_task_formation_mode" in _check_names("t_aa_teaching_task"):
        op.drop_constraint(
            "ck_aa_teaching_task_formation_mode",
            "t_aa_teaching_task",
            type_="check",
        )
    if "formation_mode" in _columns("t_aa_teaching_task"):
        op.drop_column("t_aa_teaching_task", "formation_mode")

    if "uk_aa_task_batch_editable_scope" in _unique_names("t_aa_teaching_task_batch"):
        op.drop_constraint(
            "uk_aa_task_batch_editable_scope",
            "t_aa_teaching_task_batch",
            type_="unique",
        )
    if "editable_scope_key" in _columns("t_aa_teaching_task_batch"):
        op.drop_column("t_aa_teaching_task_batch", "editable_scope_key")

    if "ck_aa_program_course_formation_mode" in _check_names("t_aa_program_course"):
        op.drop_constraint(
            "ck_aa_program_course_formation_mode",
            "t_aa_program_course",
            type_="check",
        )
    columns = _columns("t_aa_program_course")
    current = columns.get("formation_mode")
    if current is not None:
        if _revision_is_current("20260817_aa_prog_expand"):
            if getattr(current.get("type"), "length", None) != 30:
                op.alter_column(
                    "t_aa_program_course",
                    "formation_mode",
                    existing_type=current["type"],
                    type_=sa.String(length=30),
                    existing_nullable=bool(current.get("nullable", True)),
                    existing_comment=current.get("comment"),
                )
        else:
            op.drop_column("t_aa_program_course", "formation_mode")
