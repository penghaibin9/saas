"""排课管理 Tier1 R2 续工：t_aa_schedule_item 加列 objection_status / objection_reason（11 号卡·排课调整）。

预发布(PRE_PUBLISHED)阶段教师对本人课表条目提出异议→学院教务员定点改排，需要在条目上记录异议状态与原因，
供「排课调整」页展示待处理清单。nullable，历史行不受影响（null=无异议）。
本轮 03/05/07/10/13 号卡（排课约束/教室可用时间/自动排课预留/排课结果/排课归档）复用既有
t_aa_schedule_rule / t_aa_schedule_item / t_aa_schedule_batch 表结构，不新增列。
幂等：inspect 判列存在再加。

Revision ID: aa_pkgl_tier1_r2
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_pkgl_tier1_r2"
down_revision = "aa_orgs_tier1_r2"
branch_labels = None
depends_on = None

TABLE = "t_aa_schedule_item"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def _idx(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    cols = _cols(bind)
    if "objection_status" not in cols:
        op.add_column(TABLE, sa.Column("objection_status", sa.String(20), nullable=True,
                                       comment="11号卡·排课调整：教师异议状态 PENDING=待改排；null=无异议"))
    if "objection_reason" not in cols:
        op.add_column(TABLE, sa.Column("objection_reason", sa.String(500), nullable=True,
                                       comment="教师异议原因（≥5字）"))
    if "ix_t_aa_schedule_item_objection_status" not in _idx(bind):
        op.create_index("ix_t_aa_schedule_item_objection_status", TABLE, ["objection_status"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    if "ix_t_aa_schedule_item_objection_status" in _idx(bind):
        op.drop_index("ix_t_aa_schedule_item_objection_status", table_name=TABLE)
    cols = _cols(bind)
    if "objection_reason" in cols:
        op.drop_column(TABLE, "objection_reason")
    if "objection_status" in cols:
        op.drop_column(TABLE, "objection_status")
