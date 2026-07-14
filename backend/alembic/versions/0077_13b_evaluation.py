"""13B 教学评价：建 5 表（评教批次/应评任务/评价记录/评价结果/评价申诉）。

学生评教匿名：record 不存 evaluator_id（架构级匿名，D-04）。全新业务表，downgrade 逆序 drop。

Revision ID: 0077_13b_evaluation
Revises: 0076_13b_scheduling
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0077_13b_evaluation"
down_revision = "0076_13b_scheduling"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_evaluation_batch"):
        op.create_table(
            "t_aa_evaluation_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("scope_json", sa.String(2000)),
            sa.Column("template_json", sa.String(4000)),
            sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("window_start", sa.DateTime()),
            sa.Column("window_end", sa.DateTime()),
            sa.Column("result_published_at", sa.DateTime()),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON)
        op.create_index("ix_aa_eval_batch_status", "t_aa_evaluation_batch", ["tenant_id", "status"])

    if not _has(bind, "t_aa_evaluation_task"):
        op.create_table(
            "t_aa_evaluation_task", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("teaching_task_id", sa.BigInteger()),
            sa.Column("course_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("evaluator_type", sa.String(20), nullable=False, server_default="STUDENT"),
            sa.Column("evaluator_key", sa.String(100)),
            sa.Column("submitted_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            *_COMMON)
        op.create_index("ix_aa_eval_task_batch", "t_aa_evaluation_task", ["tenant_id", "batch_id", "evaluator_type"])

    if not _has(bind, "t_aa_evaluation_record"):
        op.create_table(
            "t_aa_evaluation_record", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("task_id", sa.BigInteger(), nullable=False),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("evaluator_type", sa.String(20), nullable=False, server_default="STUDENT"),
            sa.Column("answers_json", sa.String(4000)),
            sa.Column("objective_score", sa.Numeric(5, 2)),
            sa.Column("comment", sa.String(1000)),
            *_COMMON)
        op.create_index("ix_aa_eval_record_task", "t_aa_evaluation_record", ["tenant_id", "task_id"])

    if not _has(bind, "t_aa_evaluation_result"):
        op.create_table(
            "t_aa_evaluation_result", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("teaching_task_id", sa.BigInteger()),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("course_name", sa.String(200)),
            sa.Column("student_avg", sa.Numeric(5, 2)),
            sa.Column("student_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("level", sa.String(20)),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "batch_id", "teaching_task_id", name="uk_aa_eval_result"))
        op.create_index("ix_aa_eval_result_teacher", "t_aa_evaluation_result", ["tenant_id", "teacher_key"])

    if not _has(bind, "t_aa_evaluation_appeal"):
        op.create_table(
            "t_aa_evaluation_appeal", *_pk_tenant(),
            sa.Column("result_id", sa.BigInteger(), nullable=False),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("reason", sa.String(1000)),
            sa.Column("review_reason", sa.String(1000)),
            sa.Column("current_node", sa.String(50)),
            sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
            *_COMMON)
        op.create_index("ix_aa_eval_appeal_result", "t_aa_evaluation_appeal", ["tenant_id", "result_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_evaluation_appeal", "t_aa_evaluation_result", "t_aa_evaluation_record",
              "t_aa_evaluation_task", "t_aa_evaluation_batch"):
        if _has(bind, t):
            op.drop_table(t)
