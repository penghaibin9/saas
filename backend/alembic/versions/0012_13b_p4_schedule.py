"""13B-P4: 课表 batch + item 2 表（三重冲突检测 + 单双周）

Revision ID: 0012_13b_p4_schedule
Revises: 0011_13b_p3_course_teaching_task
Create Date: 2026-07-06

课表项含 weekday/slot_no/start_week/end_week/week_parity(单双周)/classroom；教师/班级/教室三重冲突。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0012_13b_p4_schedule"
down_revision = "0011_13b_p3_course_teaching_task"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")
SB = "t_aa_schedule_batch"
SI = "t_aa_schedule_item"


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


def _create(bind, table, cols, indexes=()):
    if _has(bind, table):
        return
    op.create_table(table, *cols)
    for ix in indexes:
        op.create_index(f"ix_{table}_{ix}", table, [ix])


def upgrade() -> None:
    bind = op.get_bind()

    _create(bind, SB, _pk_tenant(
        sa.Column("term_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_name", sa.String(length=200), nullable=False),
        sa.Column("college_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        *_common_cols(),
    ), indexes=("tenant_id", "term_id", "college_id", "status"))

    _create(bind, SI, _pk_tenant(
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_name", sa.String(length=200), nullable=True),
        sa.Column("class_id", sa.BigInteger(), nullable=True),
        sa.Column("class_name", sa.String(length=100), nullable=True),
        sa.Column("teacher_key", sa.String(length=100), nullable=True),
        sa.Column("teacher_name", sa.String(length=100), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("slot_no", sa.Integer(), nullable=False),
        sa.Column("start_week", sa.Integer(), nullable=False),
        sa.Column("end_week", sa.Integer(), nullable=False),
        sa.Column("week_parity", sa.String(length=10), nullable=False),
        sa.Column("classroom_text", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        *_common_cols(),
    ), indexes=("tenant_id", "batch_id", "class_id", "teacher_key", "classroom_text", "status"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (SI, SB):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
