"""13B-R1 成绩审核发布更正：状态机留痕列 + 更正追溯列 + t_acad_grade.source

Revision ID: 0068_13b_r1_grade_review
Revises: 0067_13a_affairs_attachment
Create Date: 2026-07-14

加列（幂等，不改旧列，不新建平行表——遵循《13A-13B-数据表与迁移策略草案.md》§4.5/§4.8）：
- t_aa_grade_task：submitted_at/college_reviewed_at/college_reviewer_id/academic_reviewed_at/
  academic_reviewer_id/return_reason/workflow_instance_id（审核链路留痕；teacher_key 列 0013 已建，不重复加）
- t_aa_grade_record：source（LEGACY/PUBLISH/CHANGE/MANUAL）、
  prev_usual_score/prev_final_score/prev_total_score/change_reason/change_by/change_at/version_no
  （更正 append-only 追溯）、exception_flag（NORMAL/ABSENT/DEFERRED/EXEMPT，缺考/缓考/免修互斥标记）
- t_acad_grade：source（LEGACY/PUBLISH/CHANGE/MANUAL），历史行回填 LEGACY，解决新旧写路径
  pass_status 值域不一致问题（新写路径统一产出 PASSED/FAILED，不再用 FAIL 简写）

回滚：drop 以上新增列（存在才删），不影响旧列与既有数据。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0068_13b_r1_grade_review"
down_revision = "0067_13a_affairs_attachment"
branch_labels = None
depends_on = None

TASK = "t_aa_grade_task"
RECORD = "t_aa_grade_record"
GRADE = "t_acad_grade"


def _cols(bind, table) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()

    task_cols = _cols(bind, TASK)
    if "submitted_at" not in task_cols:
        op.add_column(TASK, sa.Column("submitted_at", sa.DateTime(), nullable=True))
    if "college_reviewed_at" not in task_cols:
        op.add_column(TASK, sa.Column("college_reviewed_at", sa.DateTime(), nullable=True))
    if "college_reviewer_id" not in task_cols:
        op.add_column(TASK, sa.Column("college_reviewer_id", sa.BigInteger(), nullable=True))
    if "academic_reviewed_at" not in task_cols:
        op.add_column(TASK, sa.Column("academic_reviewed_at", sa.DateTime(), nullable=True))
    if "academic_reviewer_id" not in task_cols:
        op.add_column(TASK, sa.Column("academic_reviewer_id", sa.BigInteger(), nullable=True))
    if "return_reason" not in task_cols:
        op.add_column(TASK, sa.Column("return_reason", sa.String(length=500), nullable=True))
    if "workflow_instance_id" not in task_cols:
        op.add_column(TASK, sa.Column("workflow_instance_id", sa.BigInteger(), nullable=True))

    rec_cols = _cols(bind, RECORD)
    if "source" not in rec_cols:
        op.add_column(RECORD, sa.Column("source", sa.String(length=20), nullable=True,
                                        server_default="LEGACY", comment="LEGACY/PUBLISH/CHANGE/MANUAL"))
    if "prev_usual_score" not in rec_cols:
        op.add_column(RECORD, sa.Column("prev_usual_score", sa.Integer(), nullable=True))
    if "prev_final_score" not in rec_cols:
        op.add_column(RECORD, sa.Column("prev_final_score", sa.Integer(), nullable=True))
    if "prev_total_score" not in rec_cols:
        op.add_column(RECORD, sa.Column("prev_total_score", sa.Integer(), nullable=True))
    if "change_reason" not in rec_cols:
        op.add_column(RECORD, sa.Column("change_reason", sa.String(length=500), nullable=True))
    if "change_by" not in rec_cols:
        op.add_column(RECORD, sa.Column("change_by", sa.BigInteger(), nullable=True))
    if "change_at" not in rec_cols:
        op.add_column(RECORD, sa.Column("change_at", sa.DateTime(), nullable=True))
    if "version_no" not in rec_cols:
        op.add_column(RECORD, sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
    if "exception_flag" not in rec_cols:
        op.add_column(RECORD, sa.Column("exception_flag", sa.String(length=20), nullable=True,
                                        server_default="NORMAL", comment="NORMAL/ABSENT/DEFERRED/EXEMPT"))

    grade_cols = _cols(bind, GRADE)
    if "source" not in grade_cols:
        op.add_column(GRADE, sa.Column("source", sa.String(length=20), nullable=True,
                                       server_default="LEGACY", comment="LEGACY/PUBLISH/CHANGE/MANUAL"))
        op.execute(f"UPDATE {GRADE} SET source = 'LEGACY' WHERE source IS NULL")


def downgrade():
    bind = op.get_bind()

    grade_cols = _cols(bind, GRADE)
    if "source" in grade_cols:
        op.drop_column(GRADE, "source")

    rec_cols = _cols(bind, RECORD)
    for c in ("exception_flag", "version_no", "change_at", "change_by", "change_reason",
              "prev_total_score", "prev_final_score", "prev_usual_score", "source"):
        if c in rec_cols:
            op.drop_column(RECORD, c)

    task_cols = _cols(bind, TASK)
    for c in ("workflow_instance_id", "return_reason", "academic_reviewer_id", "academic_reviewed_at",
              "college_reviewer_id", "college_reviewed_at", "submitted_at"):
        if c in task_cols:
            op.drop_column(TASK, c)
