"""教学评价多来源:评价结果表新增 自评/同行/督导 分数 + 加权综合分（对标正方 教师端5.x 多角色评价）。

- t_aa_evaluation_result 新增：self_score / peer_avg / peer_count / supervisor_avg /
  supervisor_count / composite_score。

历史数据零影响：新增列均可空或默认0（既有结果仅学生均分，综合分核算时回填）。
回滚 drop 六列；幂等 inspect 判列。

Revision ID: 0097_aa_eval_multisource
Revises: 0096_aa_grade_recheck
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0097_aa_eval_multisource"
down_revision = "0096_aa_grade_recheck"
branch_labels = None
depends_on = None

TABLE = "t_aa_evaluation_result"

_ADD = [
    ("self_score", sa.Column("self_score", sa.Numeric(5, 2), nullable=True, comment="教师自评分")),
    ("peer_avg", sa.Column("peer_avg", sa.Numeric(5, 2), nullable=True, comment="同行评价均分")),
    ("peer_count", sa.Column("peer_count", sa.Integer(), nullable=False, server_default="0")),
    ("supervisor_avg", sa.Column("supervisor_avg", sa.Numeric(5, 2), nullable=True, comment="督导评价均分")),
    ("supervisor_count", sa.Column("supervisor_count", sa.Integer(), nullable=False, server_default="0")),
    ("composite_score", sa.Column("composite_score", sa.Numeric(5, 2), nullable=True, comment="多来源加权综合分")),
]


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    if not cols:
        return
    for name, col in _ADD:
        if name not in cols:
            op.add_column(TABLE, col)


def downgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind)
    for name, _ in reversed(_ADD):
        if name in cols:
            op.drop_column(TABLE, name)
