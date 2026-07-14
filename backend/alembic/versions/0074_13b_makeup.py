"""13B-SM-12 补考重修免修：建 3 表（makeup_batch/retake_apply/exemption）+ 台账两表加列。

新建 t_aa_makeup_batch / t_aa_retake_apply / t_aa_exemption（锁名，前两者锁名清单已列，exemption 亦锁名）。
t_acad_makeup += batch_id/final_score；t_acad_retake += apply_id（nullable，历史行零回填）。
幂等：inspect 判表/列存在再建/增。

Revision ID: 0074_13b_makeup
Revises: 0073_13b_exam
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0074_13b_makeup"
down_revision = "0073_13b_exam"
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


def _cols(bind, t):
    return {c["name"] for c in inspect(bind).get_columns(t)} if _has(bind, t) else set()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_makeup_batch"):
        op.create_table(
            "t_aa_makeup_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("term_code", sa.String(50)),
            sa.Column("exam_batch_ref", sa.BigInteger()),
            sa.Column("score_rule", sa.String(20), nullable=False, server_default="CAP60"),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("remark", sa.String(500)),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON)
        op.create_index("ix_aa_makeup_batch_status", "t_aa_makeup_batch", ["tenant_id", "status"])

    if not _has(bind, "t_aa_retake_apply"):
        op.create_table(
            "t_aa_retake_apply", *_pk_tenant(),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("acad_student_id", sa.BigInteger()),
            sa.Column("course_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("term_code", sa.String(50)),
            sa.Column("reason", sa.String(500)),
            sa.Column("retake_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("review_reason", sa.String(500)),
            sa.Column("teaching_task_ref", sa.BigInteger()),
            sa.Column("workflow_instance_id", sa.BigInteger()),
            sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
            *_COMMON)
        op.create_index("ix_aa_retake_student", "t_aa_retake_apply", ["tenant_id", "student_id", "status"])

    if not _has(bind, "t_aa_exemption"):
        op.create_table(
            "t_aa_exemption", *_pk_tenant(),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("course_id", sa.BigInteger()),
            sa.Column("course_name", sa.String(200)),
            sa.Column("term_code", sa.String(50)),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("teacher_key", sa.String(100)),
            sa.Column("reason", sa.String(500)),
            sa.Column("material_file_ids", sa.String(1000)),
            sa.Column("current_node", sa.String(50)),
            sa.Column("return_reason", sa.String(500)),
            sa.Column("workflow_instance_id", sa.BigInteger()),
            sa.Column("status", sa.String(30), nullable=False, server_default="SUBMITTED"),
            *_COMMON)
        op.create_index("ix_aa_exemption_student", "t_aa_exemption", ["tenant_id", "student_id", "status"])

    # 台账加列
    mc = _cols(bind, "t_acad_makeup")
    if mc and "batch_id" not in mc:
        op.add_column("t_acad_makeup", sa.Column("batch_id", sa.BigInteger(), nullable=True))
    if mc and "final_score" not in mc:
        op.add_column("t_acad_makeup", sa.Column("final_score", sa.Integer(), nullable=True))
    rc = _cols(bind, "t_acad_retake")
    if rc and "apply_id" not in rc:
        op.add_column("t_acad_retake", sa.Column("apply_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for t, col in (("t_acad_retake", "apply_id"), ("t_acad_makeup", "final_score"), ("t_acad_makeup", "batch_id")):
        if col in _cols(bind, t):
            op.drop_column(t, col)
    for t in ("t_aa_exemption", "t_aa_retake_apply", "t_aa_makeup_batch"):
        if _has(bind, t):
            op.drop_table(t)
