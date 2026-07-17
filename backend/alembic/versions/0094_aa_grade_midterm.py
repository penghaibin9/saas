"""成绩分项扩展:新增「期中」分项(对标正方 成绩比例设置/成绩录入 的多分项按比例合成)。

- t_aa_grade_task.midterm_ratio        期中占比%,NOT NULL DEFAULT 0(=0 时退化为「平时+期末」,旧任务合成结果完全不变)
- t_aa_grade_record.midterm_score      期中分(期中占比>0时启用),可空
- t_aa_grade_record.prev_midterm_score 成绩更正留痕的期中原值,可空

历史数据零影响:midterm_ratio 默认 0,既有任务合成公式 total=平时*占比+期末*占比 结果不变;
midterm_score/prev_midterm_score 可空。回滚 drop 三列;幂等 inspect 判列。

Revision ID: 0094_aa_grade_midterm
Revises: 0093_aa_recognition_picker_attach
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0094_aa_grade_midterm"
down_revision = "0093_aa_recognition_picker_attach"
branch_labels = None
depends_on = None

TASK = "t_aa_grade_task"
RECORD = "t_aa_grade_record"


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    task_cols = _cols(bind, TASK)
    if task_cols and "midterm_ratio" not in task_cols:
        op.add_column(TASK, sa.Column("midterm_ratio", sa.Integer(), nullable=False,
                                      server_default="0", comment="期中占比%(0=不启用期中)"))
    rec_cols = _cols(bind, RECORD)
    if rec_cols and "midterm_score" not in rec_cols:
        op.add_column(RECORD, sa.Column("midterm_score", sa.Integer(), nullable=True,
                                        comment="期中分(期中占比>0时启用)"))
    if rec_cols and "prev_midterm_score" not in rec_cols:
        op.add_column(RECORD, sa.Column("prev_midterm_score", sa.Integer(), nullable=True,
                                        comment="成绩更正的期中原值"))


def downgrade() -> None:
    bind = op.get_bind()
    rec_cols = _cols(bind, RECORD)
    if "prev_midterm_score" in rec_cols:
        op.drop_column(RECORD, "prev_midterm_score")
    if "midterm_score" in rec_cols:
        op.drop_column(RECORD, "midterm_score")
    task_cols = _cols(bind, TASK)
    if "midterm_ratio" in task_cols:
        op.drop_column(TASK, "midterm_ratio")
