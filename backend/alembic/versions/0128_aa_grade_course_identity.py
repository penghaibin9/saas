"""V2-04 正式成绩保存课程身份、课程版本、修读次数与业务来源。

历史 t_acad_grade / t_acad_makeup 行保持 NULL，不在迁移中按课程名猜测；应用层提供显式回填与欠账报告。

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

_GRADE = "t_acad_grade"
_MAKEUP = "t_acad_makeup"


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _columns(bind, table):
    return {row["name"] for row in inspect(bind).get_columns(table)} if table in _tables(bind) else set()


def _indexes(bind, table):
    return {row["name"] for row in inspect(bind).get_indexes(table)} if table in _tables(bind) else set()


def _uniques(bind, table):
    return {row["name"] for row in inspect(bind).get_unique_constraints(table)} if table in _tables(bind) else set()


def _add_column(bind, table, column):
    if table in _tables(bind) and column.name not in _columns(bind, table):
        op.add_column(table, column)


def _ensure_index(bind, table, name, columns):
    if table in _tables(bind) and name not in _indexes(bind, table):
        op.create_index(name, table, columns)


def _ensure_unique(bind, table, name, columns):
    if table in _tables(bind) and name not in _uniques(bind, table) and name not in _indexes(bind, table):
        op.create_unique_constraint(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()

    for column in (
        sa.Column("course_id", sa.BigInteger(), nullable=True, comment="→ t_aa_course.id，具体课程版本行"),
        sa.Column("course_code", sa.String(length=50), nullable=True, comment="课程代码快照"),
        sa.Column("course_version", sa.Integer(), nullable=True, comment="课程库版本快照"),
        sa.Column("attempt_no", sa.Integer(), nullable=True, comment="第几次修读；补考/清考继承原修读次数"),
        sa.Column("grade_task_id", sa.BigInteger(), nullable=True, comment="→ t_aa_grade_task"),
        sa.Column("grade_record_id", sa.BigInteger(), nullable=True, comment="→ t_aa_grade_record；正常发布来源唯一"),
        sa.Column("source_biz_type", sa.String(length=50), nullable=True, comment="MAKEUP/RECOGNITION/EXEMPTION等"),
        sa.Column("source_biz_id", sa.BigInteger(), nullable=True, comment="业务来源记录ID"),
        sa.Column("teaching_task_id", sa.BigInteger(), nullable=True, comment="→ t_aa_teaching_task"),
        sa.Column("teaching_class_id", sa.BigInteger(), nullable=True, comment="→ t_aa_teaching_class"),
        sa.Column("roster_version_id", sa.BigInteger(), nullable=True, comment="发布时采用的正式名单版本"),
    ):
        _add_column(bind, _GRADE, column)

    _ensure_unique(bind, _GRADE, "uk_acad_grade_source_record", ["tenant_id", "grade_record_id"])
    _ensure_unique(bind, _GRADE, "uk_acad_grade_source_biz", ["tenant_id", "source_biz_type", "source_biz_id"])
    _ensure_index(
        bind, _GRADE, "ix_acad_grade_course_attempt",
        ["tenant_id", "acad_student_id", "course_id", "attempt_no", "record_status"],
    )
    _ensure_index(bind, _GRADE, "ix_acad_grade_course_code", ["tenant_id", "course_code", "course_version"])
    _ensure_index(bind, _GRADE, "ix_acad_grade_grade_task", ["tenant_id", "grade_task_id"])
    _ensure_index(bind, _GRADE, "ix_acad_grade_teaching_task", ["tenant_id", "teaching_task_id"])
    _ensure_index(bind, _GRADE, "ix_acad_grade_teaching_class", ["tenant_id", "teaching_class_id"])
    _ensure_index(bind, _GRADE, "ix_acad_grade_source_biz", ["tenant_id", "source_biz_type", "source_biz_id"])

    for column in (
        sa.Column("origin_grade_id", sa.BigInteger(), nullable=True, comment="→ t_acad_grade 原失败成绩"),
        sa.Column("course_id", sa.BigInteger(), nullable=True, comment="原失败成绩具体课程版本"),
        sa.Column("course_code", sa.String(length=50), nullable=True),
        sa.Column("course_version", sa.Integer(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=True, comment="继承原修读次数"),
    ):
        _add_column(bind, _MAKEUP, column)
    _ensure_index(bind, _MAKEUP, "ix_acad_makeup_origin_grade", ["tenant_id", "origin_grade_id"])
    _ensure_index(
        bind, _MAKEUP, "ix_acad_makeup_course_attempt",
        ["tenant_id", "acad_student_id", "course_id", "attempt_no"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    for name in ("ix_acad_makeup_course_attempt", "ix_acad_makeup_origin_grade"):
        if name in _indexes(bind, _MAKEUP):
            op.drop_index(name, table_name=_MAKEUP)
    for name in ("attempt_no", "course_version", "course_code", "course_id", "origin_grade_id"):
        if name in _columns(bind, _MAKEUP):
            op.drop_column(_MAKEUP, name)

    for name in (
        "ix_acad_grade_source_biz",
        "ix_acad_grade_teaching_class",
        "ix_acad_grade_teaching_task",
        "ix_acad_grade_grade_task",
        "ix_acad_grade_course_code",
        "ix_acad_grade_course_attempt",
    ):
        if name in _indexes(bind, _GRADE):
            op.drop_index(name, table_name=_GRADE)
    for name in ("uk_acad_grade_source_biz", "uk_acad_grade_source_record"):
        if name in _uniques(bind, _GRADE) or name in _indexes(bind, _GRADE):
            op.drop_constraint(name, _GRADE, type_="unique")
    for name in (
        "roster_version_id",
        "teaching_class_id",
        "teaching_task_id",
        "source_biz_id",
        "source_biz_type",
        "grade_record_id",
        "grade_task_id",
        "attempt_no",
        "course_version",
        "course_code",
        "course_id",
    ):
        if name in _columns(bind, _GRADE):
            op.drop_column(_GRADE, name)
