"""毕业清考：复用补考批次/记录表加 kind 区分。

对标商业教务系统（强智《智慧教学服务平台操作手册》6-6 毕业清考，印刷页 418-423）：
清考=毕业年级学生对"补考/重修后仍未通过课程"的最后一次考核机会，独立批次管理、
自动圈定名单、成绩回写 t_acad_grade(source=CLEARANCE)。

数据结构与补考同构，故不建新表，复用 + kind 列区分（默认 MAKEUP 与既有行为一致）：
- t_aa_makeup_batch.kind          MAKEUP/CLEARANCE
- t_aa_makeup_batch.target_grades 清考限定年级（逗号分隔）
- t_acad_makeup.kind              MAKEUP/CLEARANCE

回滚 drop 三列；幂等 inspect 判列。

Revision ID: 0088_aa_clearance_exam
Revises: 0087_aa_selection_rounds
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0088_aa_clearance_exam"
down_revision = "0087_aa_selection_rounds"
branch_labels = None
depends_on = None

T_BATCH = "t_aa_makeup_batch"
T_REC = "t_acad_makeup"


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    b = _cols(bind, T_BATCH)
    if b:
        if "kind" not in b:
            op.add_column(T_BATCH, sa.Column("kind", sa.String(20), nullable=False,
                                             server_default="MAKEUP",
                                             comment="MAKEUP 常规补考 / CLEARANCE 毕业清考"))
            op.create_index("ix_aa_makeup_batch_kind", T_BATCH, ["kind"])
        if "target_grades" not in b:
            op.add_column(T_BATCH, sa.Column("target_grades", sa.String(200), nullable=True,
                                             comment="清考限定年级(逗号分隔)"))
    r = _cols(bind, T_REC)
    if r and "kind" not in r:
        op.add_column(T_REC, sa.Column("kind", sa.String(20), nullable=False,
                                       server_default="MAKEUP",
                                       comment="MAKEUP 常规补考 / CLEARANCE 毕业清考"))
        op.create_index("ix_acad_makeup_kind", T_REC, ["kind"])


def downgrade() -> None:
    bind = op.get_bind()
    if "kind" in _cols(bind, T_REC):
        op.drop_index("ix_acad_makeup_kind", T_REC)
        op.drop_column(T_REC, "kind")
    b = _cols(bind, T_BATCH)
    if "target_grades" in b:
        op.drop_column(T_BATCH, "target_grades")
    if "kind" in b:
        op.drop_index("ix_aa_makeup_batch_kind", T_BATCH)
        op.drop_column(T_BATCH, "kind")
