"""13B-P3: 课程库 t_aa_course + 教学任务 batch/task 3 表

Revision ID: 0011_13b_p3_course_teaching_task
Revises: 0010_13b_p2_status_change_program
Create Date: 2026-07-06

课程库商业级全字段(学时构成/性质/类别/考核方式)+两级审核；教学任务(教学班/周学时)generate 幂等。
唯一键 t_aa_course(tenant,course_code,version)。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0011_13b_p3_course_teaching_task"
down_revision = "0010_13b_p2_status_change_program"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
COURSE = "t_aa_course"
TB = "t_aa_teaching_task_batch"
TT = "t_aa_teaching_task"


def _has(bind, table):
    return table in inspect(bind).get_table_names()


def _pk_tenant(*extra):
    return [sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False), *extra]


def _common_cols():
    return [sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False)]


def _create(bind, table, cols, indexes=(), uniques=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix in indexes:
        op.create_index(f"ix_{table}_{ix}", table, [ix])
    for name, ucols in uniques:
        op.create_unique_constraint(name, table, list(ucols))


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, COURSE, _pk_tenant(
        sa.Column("course_code", sa.String(length=50), nullable=False),
        sa.Column("course_name", sa.String(length=200), nullable=False),
        sa.Column("course_name_en", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("nature", sa.String(length=50), nullable=False),
        sa.Column("credit", sa.Numeric(4, 1), nullable=False),
        sa.Column("hours_total", sa.Integer(), nullable=True),
        sa.Column("hours_theory", sa.Integer(), nullable=True),
        sa.Column("hours_practice", sa.Integer(), nullable=True),
        sa.Column("hours_experiment", sa.Integer(), nullable=True),
        sa.Column("hours_computer", sa.Integer(), nullable=True),
        sa.Column("exam_mode", sa.String(length=20), nullable=False),
        sa.Column("owner_college_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("is_core", sa.Boolean(), nullable=False),
        sa.Column("prerequisite_codes_json", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prev_version_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "course_code", "owner_college_id", "status"),
       uniques=(("uk_aa_course", ("tenant_id", "course_code", "version")),))

    _create(bind, TB, _pk_tenant(
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("college_id", sa.BigInteger(), nullable=True),
        sa.Column("generate_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "term_id", "college_id", "status"))

    _create(bind, TT, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("course_code", sa.String(length=50), nullable=True),
        sa.Column("course_name", sa.String(length=200), nullable=True),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("teaching_class_code", sa.String(length=50), nullable=True),
        sa.Column("teaching_class_name", sa.String(length=200), nullable=True),
        sa.Column("is_merged", sa.Boolean(), nullable=False),
        sa.Column("teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("teacher_key", sa.String(length=100), nullable=True),
        sa.Column("teacher_name", sa.String(length=100), nullable=True),
        sa.Column("expected_students", sa.Integer(), nullable=True),
        sa.Column("weekly_hours", sa.Integer(), nullable=True),
        sa.Column("total_hours", sa.Integer(), nullable=True),
        sa.Column("start_week", sa.Integer(), nullable=True),
        sa.Column("end_week", sa.Integer(), nullable=True),
        sa.Column("confirm_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "course_id", "class_id", "teacher_id", "status"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (TT, TB, COURSE):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
