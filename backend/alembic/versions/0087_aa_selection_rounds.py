"""选课多轮次+抽签：轮次表 + 选课记录轮次外键。

对标商业教务系统（强智《智慧教学服务平台操作手册》印刷页 224-250 选课管理：
选课轮次维护/抽签/选课控制"可选可退·只可选·只可退"）的多轮次选课模型。

- 新表 t_aa_selection_round：批次内多轮次（FCFS 先到先得 / LOTTERY 抽签），
  allow_enroll/allow_drop 两布尔位表达三态选课控制。
- t_aa_selection_record.round_id：记录产生于哪个轮次；null=无轮次批次，
  行为与既有先到先得完全一致（向后兼容，存量数据零影响）。
- record.status 新增语义值 PENDING_LOTTERY/LOTTERY_LOST（列宽 String(30) 足够，无需改列）。

回滚：drop 新表与新列。幂等：inspect 判表/列。

Revision ID: 0087_aa_selection_rounds
Revises: 0086_aa_autoexam
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0087_aa_selection_rounds"
down_revision = "0086_aa_autoexam"
branch_labels = None
depends_on = None

T_ROUND = "t_aa_selection_round"
T_REC = "t_aa_selection_record"


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _cols(bind, table):
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if T_ROUND not in _tables(bind):
        op.create_table(
            T_ROUND,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("round_name", sa.String(100), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False, server_default="FCFS"),
            sa.Column("start_at", sa.DateTime()),
            sa.Column("end_at", sa.DateTime()),
            sa.Column("allow_enroll", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("allow_drop", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "batch_id", "round_no", name="uk_aa_selection_round"))
        op.create_index("ix_aa_sel_round_batch", T_ROUND, ["batch_id"])
        op.create_index("ix_aa_sel_round_status", T_ROUND, ["status"])

    rec = _cols(bind, T_REC)
    if rec and "round_id" not in rec:
        op.add_column(T_REC, sa.Column("round_id", sa.BigInteger(), nullable=True,
                                       comment="→ t_aa_selection_round；null=无轮次批次"))
        op.create_index("ix_aa_sel_rec_round", T_REC, ["round_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "round_id" in _cols(bind, T_REC):
        op.drop_index("ix_aa_sel_rec_round", T_REC)
        op.drop_column(T_REC, "round_id")
    if T_ROUND in _tables(bind):
        op.drop_table(T_ROUND)
