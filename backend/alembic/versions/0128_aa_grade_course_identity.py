"""V2-04 正式成绩保存课程身份、课程版本和修读次数。

历史 t_acad_grade 行保持 NULL，不在迁移中按课程名猜测 course_id；应用层提供显式回填与欠账报告。

Revision ID: 0128_aa_grade_course_identity
Revises: 0127_aa_teaching_class_roster
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0128_aa_grade_course_identity"
down_revision = "0127_aa_teaching_class_roster"
branch_labels = None
depends_on = None

_TABLE = "t_acad_grade"


def _columns(bind):
    return {row["name"] for row in inspect(bind).get_columns(_TABLE)}


def _indexes(bind):
    return {row["name"] for row in inspect(bind).get_indexes(_TABLE)}


def _uniques(bind):
    return {row["name"] for row in inspect(bind).get_unique_constraints(_TABLE)}


def _add_column(bind, column):
    if column.name not in _columns(bind):
        op.add_column(_TABLE, column)


def _ensure_index(bind, name, columns):
    if name not in _indexes(bind):
        op.create_index(name, _TABLE, columns)


def _ensure_unique(bind, name, columns):
    if name not in _uniques(bind) and name not in _indexes(bind):
        op.create_unique_constraint(name, _TABLE, columns)


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in set(inspect(bind).get_table_names()):
        return

    for column in (
        sa.Column("course_id", sa.BigInteger(), nullable=True, comment="→ t_aa_course.id，具体课程版本行"),
        sa.Column("course_code", sa.String(length=50), nullable=True, comment="课程代码快照"),
        sa.Column("course_version", sa.Integer(), nullable=True, comment="课程库版本快照"),
        sa.Column("attempt_no", sa.Integer(), nullable=True, comment="第几次修读；补考/清考继承原修读次数"),
        sa.Column("grade_task_id", sa.BigInteger(), nullable=True, comment="→ t_aa_grade_task"),
        sa.Column("grade_record_id", sa.BigInteger(), nullable=True, comment="→ t_aa_grade_record；正常发布来源唯一"),
        sa.Column("teaching_task_id", sa.BigInteger(), nullable=True, comment="→ t_aa_teaching_task"),
        sa.Column("teaching_class_id", sa.BigInteger(), nullable=True, comment="→ t_aa_teaching_class"),
        sa.Column("roster_version_id", sa.BigInteger(), nullable=True, comment="发布时采用的正式名单版本"),
    ):
        _add_column(bind, column)

    _ensure_unique(bind, "uk_acad_grade_source_record", ["tenant_id", "grade_record_id"])
    _ensure_index(
        bind,
        "ix_acad_grade_course_attempt",
        ["tenant_id", "acad_student_id", "course_id", "attempt_no", "record_status"],
    )
    _ensure_index(bind, "ix_acad_grade_course_code", ["tenant_id", "course_code", "course_version"])
    _ensure_index(bind, "ix_acad_grade_grade_task", ["tenant_id", "grade_task_id"])
    _ensure_index(bind, "ix_acad_grade_teaching_task", ["tenant_id", "teaching_task_id"])
    _ensure_index(bind, "ix_acad_grade_teaching_class", ["tenant_id", "teaching_class_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in set(inspect(bind).get_table_names()):
        return
    for name in (
        "ix_acad_grade_teaching_class",
        "ix_acad_grade_teaching_task",
        "ix_acad_grade_grade_task",
        "ix_acad_grade_course_code",
        "ix_acad_grade_course_attempt",
    ):
        if name in _indexes(bind):
            op.drop_index(name, table_name=_TABLE)
    if "uk_acad_grade_source_record" in _uniques(bind) or "uk_acad_grade_source_record" in _indexes(bind):
        op.drop_constraint("uk_acad_grade_source_record", _TABLE, type_="unique")
    for name in (
        "roster_version_id",
        "teaching_class_id",
        "teaching_task_id",
        "grade_record_id",
        "grade_task_id",
        "attempt_no",
        "course_version",
        "course_code",
        "course_id",
    ):
        if name in _columns(bind):
            op.drop_column(_TABLE, name)
