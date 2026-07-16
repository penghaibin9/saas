"""自动排考：考场来源标记。

对标商业教务系统（强智《智慧教学服务平台操作手册》第5章考务管理，印刷页 271-350：
自动编排考场 / 编排座位号 / 自动安排监考）的自动排考落地前置。

- t_aa_exam_room.source  MANUAL/AUTO，默认 MANUAL 与既有行为一致。
  自动排考重排时只清 AUTO 考场（连带其座位与监考），人工编排的考场绝不覆盖——
  与 0085 课表项 source 同一纪律。

回滚：drop 本迁移新增列，不丢既有考场数据。幂等：inspect 判列。

Revision ID: 0086_aa_autoexam
Revises: 0085_aa_scheduling_engine
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0086_aa_autoexam"
down_revision = "0085_aa_scheduling_engine"
branch_labels = None
depends_on = None

T_ROOM = "t_aa_exam_room"


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _cols(bind, T_ROOM)
    if cols and "source" not in cols:
        op.add_column(T_ROOM, sa.Column("source", sa.String(20), nullable=False,
                                        server_default="MANUAL",
                                        comment="MANUAL/AUTO 手工/自动排考"))
        op.create_index("ix_aa_exam_room_source", T_ROOM, ["source"])


def downgrade() -> None:
    bind = op.get_bind()
    if "source" in _cols(bind, T_ROOM):
        op.drop_index("ix_aa_exam_room_source", T_ROOM)
        op.drop_column(T_ROOM, "source")
