"""课堂考勤增强:新增「点名类别」(对标正方 教师教学点名 2.4/教学点名查询 4.19 的点名类别维度)。

- t_aa_attendance_session.session_type  点名类别:常规/实训/晚自习/其他,可空(空=常规)

历史数据零影响:可空列,既有场次视为常规。回滚 drop 列;幂等 inspect 判列。

Revision ID: 0095_aa_attendance_type
Revises: 0094_aa_grade_midterm
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0095_aa_attendance_type"
down_revision = "0094_aa_grade_midterm"
branch_labels = None
depends_on = None

TABLE = "t_aa_attendance_session"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    if cols and "session_type" not in cols:
        op.add_column(TABLE, sa.Column("session_type", sa.String(20), nullable=True,
                                       comment="点名类别:常规/实训/晚自习/其他(空=常规)"))


def downgrade() -> None:
    bind = op.get_bind()
    if "session_type" in _cols(bind):
        op.drop_column(TABLE, "session_type")
