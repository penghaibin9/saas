"""13B-SM-09 选课管理：建三表（batch 头 / course 供给 / record 记录），不改存量表。

t_aa_selection_batch  选课批次头（6 态）
t_aa_selection_course 批次内课程供给项（容量/限选/取消，selected_count 行锁扣减）
t_aa_selection_record 学生选课记录（4 态，退课/复选复用同一行）

全新业务表，无存量兼容负担；downgrade 逐表 drop。幂等：inspect 判表存在再建/删。

Revision ID: 0072_13b_p7_selection
Revises: 0071_13b_r2_schedule_change
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0072_13b_p7_selection"
down_revision = "0071_13b_r2_schedule_change"
branch_labels = None
depends_on = None

BATCH = "t_aa_selection_batch"
COURSE = "t_aa_selection_course"
RECORD = "t_aa_selection_record"


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, BATCH):
        op.create_table(
            BATCH,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("term_id", sa.BigInteger(), nullable=True),
            sa.Column("batch_name", sa.String(length=200), nullable=False),
            sa.Column("select_start_at", sa.DateTime(), nullable=True),
            sa.Column("select_end_at", sa.DateTime(), nullable=True),
            sa.Column("apply_scope_json", sa.String(length=2000), nullable=True),
            sa.Column("rule_json", sa.String(length=2000), nullable=True),
            sa.Column("remark", sa.String(length=500), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_name", "term_id", name="uk_aa_selection_batch"),
        )
        op.create_index("ix_aa_sel_batch_term", BATCH, ["tenant_id", "term_id"])
        op.create_index("ix_aa_sel_batch_status", BATCH, ["tenant_id", "status"])

    if not _has(bind, COURSE):
        op.create_table(
            COURSE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("course_name", sa.String(length=200), nullable=True),
            sa.Column("teaching_task_id", sa.BigInteger(), nullable=True),
            sa.Column("teacher_key", sa.String(length=100), nullable=True),
            sa.Column("teacher_name", sa.String(length=100), nullable=True),
            sa.Column("credit", sa.Numeric(4, 1), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("min_capacity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", "course_id", "teaching_task_id",
                                name="uk_aa_selection_course"),
        )
        op.create_index("ix_aa_sel_course_batch", COURSE, ["tenant_id", "batch_id", "status"])
        op.create_index("ix_aa_sel_course_teacher", COURSE, ["tenant_id", "teacher_key"])

    if not _has(bind, RECORD):
        op.create_table(
            RECORD,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("selection_course_id", sa.BigInteger(), nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=True),
            sa.Column("course_name", sa.String(length=200), nullable=True),
            sa.Column("credit", sa.Numeric(4, 1), nullable=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(length=50), nullable=True),
            sa.Column("student_name", sa.String(length=100), nullable=True),
            sa.Column("enrolled_at", sa.DateTime(), nullable=True),
            sa.Column("dropped_at", sa.DateTime(), nullable=True),
            sa.Column("adjust_reason", sa.String(length=500), nullable=True),
            sa.Column("re_enroll", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="SELECTED"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", "selection_course_id", "student_id",
                                name="uk_aa_selection_record"),
        )
        op.create_index("ix_aa_sel_record_student", RECORD, ["tenant_id", "student_id", "batch_id"])
        op.create_index("ix_aa_sel_record_course", RECORD, ["tenant_id", "selection_course_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in (RECORD, COURSE, BATCH):
        if _has(bind, t):
            op.drop_table(t)
