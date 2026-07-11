"""毕设成果附件：t_gd_final 增 attachments_json（论文/材料 file_id 回链 t_file_object）

Revision ID: 0043_gd_final_attachments
Revises: 0042_13a_class_material_counselor_eval
Create Date: 2026-07-11

说明：成果批阅移动端需真实附件预览/下载。t_gd_final 原缺附件列，本迁移补 attachments_json，
存文件中心 t_file_object.id 列表（与开题 t_gd_proposal.attachments_json 一致）。幂等：列已存在则跳过。
注：本仓库存在实习域未提交迁移（0035-0041），完整 alembic upgrade 需其先落库；测试用 create_all 不受影响。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0043_gd_final_attachments"
down_revision = "0042_13a_class_material_counselor_eval"
branch_labels = None
depends_on = None

TABLE = "t_gd_final"
COLUMN = "attachments_json"


def _has_column(bind, table, column):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return True  # 表不存在时不报错（跳过），交由建表迁移负责
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, TABLE, COLUMN):
        op.add_column(TABLE, sa.Column(COLUMN, sa.JSON(), nullable=True,
                                       comment="论文/材料附件 file_id 列表（t_file_object.id）"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if TABLE in insp.get_table_names() and COLUMN in {c["name"] for c in insp.get_columns(TABLE)}:
        op.drop_column(TABLE, COLUMN)
