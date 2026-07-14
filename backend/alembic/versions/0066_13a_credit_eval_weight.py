"""13A 加权引擎：二课积分类目权重 + 辅导员考评加权总分

Revision ID: 0066_13a_credit_eval_weight
Revises: 0065_13a_work_study_monthly
Create Date: 2026-07-14

加列（幂等，不改旧列）：
- t_affairs_credit_category.weight      二课类目系数（默认 1.00；成绩单加权汇总用，原始明细不变）
- t_affairs_counselor_eval.weighted_total_score  考评加权总分（Σscore×weight/Σweight，附加列，不改 total_score）
回滚：drop 两列（存在才删）。历史行 weight 缺省 1.00 / weighted_total_score 为 NULL（前端回退原始总分）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0066_13a_credit_eval_weight"
down_revision = "0065_13a_work_study_monthly"
branch_labels = None
depends_on = None

CAT = "t_affairs_credit_category"
EVAL = "t_affairs_counselor_eval"


def _cols(bind, table) -> set[str]:
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if "weight" not in _cols(bind, CAT):
        op.add_column(CAT, sa.Column("weight", sa.Numeric(precision=6, scale=2),
                                     nullable=True, server_default="1.00",
                                     comment="类目加权系数（成绩单加权汇总；默认1）"))
    if "weighted_total_score" not in _cols(bind, EVAL):
        op.add_column(EVAL, sa.Column("weighted_total_score", sa.Numeric(precision=8, scale=2),
                                      nullable=True, comment="按指标权重加权总分（附加列，不改 total_score）"))


def downgrade():
    bind = op.get_bind()
    if "weighted_total_score" in _cols(bind, EVAL):
        op.drop_column(EVAL, "weighted_total_score")
    if "weight" in _cols(bind, CAT):
        op.drop_column(CAT, "weight")
