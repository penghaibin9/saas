"""校历节次 Tier1 R2：建表 t_aa_class_time_band（上课时间段，节次的实际钟点，支持按校区/生效
日期区间配置多套作息，如夏令/冬令时间）。

全新业务表，downgrade drop。幂等：inspect 判表。下游节假日配置/补课日配置/节次管理/教学周日历/
校历发布/校历归档均复用既有 t_aa_calendar_event / t_aa_time_slot / t_aa_term（不新建表）。

Revision ID: aa_calperiod_tier1_r2
Revises: aa_jxrw_tier1_r1

本 worktree 基线（83ba674 ff-forward 后）实测 alembic 单头为 aa_jxrw_tier1_r1；总控合并多个
并行分支时会统一重新排序 down_revision 链，本文件按当前实测链尾登记。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_calperiod_tier1_r2"
down_revision = "aa_jxrw_tier1_r1"
branch_labels = None
depends_on = None

TABLE = "t_aa_class_time_band"


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("slot_id", sa.BigInteger(), nullable=False),
            sa.Column("band_name", sa.String(50)),
            sa.Column("campus_code", sa.String(50)),
            sa.Column("effective_start", sa.DateTime()),
            sa.Column("effective_end", sa.DateTime()),
            sa.Column("start_time", sa.String(10)),
            sa.Column("end_time", sa.String(10)),
            sa.Column("status", sa.String(50), nullable=False, server_default="ENABLED"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_aa_time_band_tenant", TABLE, ["tenant_id"])
        op.create_index("ix_aa_time_band_slot", TABLE, ["slot_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, TABLE):
        op.drop_table(TABLE)
