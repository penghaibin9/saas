"""微信一键登录：t_user 增加 wx_openid 唯一列

Revision ID: 0058_user_wx_openid
Revises: 0057_13a_league_dev
Create Date: 2026-07-14

给 t_user 增加 wx_openid（微信小程序 openid，全局唯一，一个 openid 绑一个账号）。
可空、附唯一索引；纯增量列，不动既有数据，历史账号 wx_openid 为 NULL（未绑定）。
幂等：列已存在则跳过。回滚：downgrade 逆序 drop 索引与列（无历史数据零风险）。

注意（多头协调）：本迁移 down_revision 指向本会话时的 alembic head 0057_13a_league_dev。
若并行分支已另加 head，合并时用 `alembic merge heads` 或将本文件 down_revision 改指最终 head 再 upgrade。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0058_user_wx_openid"
down_revision = "0057_13a_league_dev"
branch_labels = None
depends_on = None

TABLE = "t_user"
COL = "wx_openid"
IDX = "ix_t_user_wx_openid"


def _has_column(bind, table, col) -> bool:
    if table not in inspect(bind).get_table_names():
        return False
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def _has_index(bind, table, idx) -> bool:
    if table not in inspect(bind).get_table_names():
        return False
    return idx in {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, TABLE, COL):
        op.add_column(TABLE, sa.Column(COL, sa.String(length=64), nullable=True,
                                       comment="微信小程序 openid（一键登录绑定；全局唯一）"))
    if not _has_index(bind, TABLE, IDX):
        op.create_index(IDX, TABLE, [COL], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, TABLE, IDX):
        op.drop_index(IDX, table_name=TABLE)
    if _has_column(bind, TABLE, COL):
        op.drop_column(TABLE, COL)
