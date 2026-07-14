"""13A-C 违纪送达与申诉：t_affairs_discipline_case 加送达列 + 新表 t_affairs_discipline_appeal

Revision ID: 0059_13a_discipline_deliver_appeal
Revises: 0058_13a_funding_disbursement
Create Date: 2026-07-14

case 表加 3 列(delivered_at/delivery_method/delivery_remark)——加列不改旧列，旧行 NULL 不影响投影对账。
新表 discipline_appeal。幂等：列/表已存在则跳过。回滚：drop 表 + drop 列。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0059_13a_discipline_deliver_appeal"
down_revision = "0058_13a_funding_disbursement"
branch_labels = None
depends_on = None

T_CASE = "t_affairs_discipline_case"
T_APPEAL = "t_affairs_discipline_appeal"
_NEW_COLS = {"delivered_at": sa.Column("delivered_at", sa.DateTime()),
             "delivery_method": sa.Column("delivery_method", sa.String(length=30)),
             "delivery_remark": sa.Column("delivery_remark", sa.String(length=500))}


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def _cols(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)} if _has(bind, table) else set()


def _common_cols():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade():
    bind = op.get_bind()
    have = _cols(bind, T_CASE)
    for name, col in _NEW_COLS.items():
        if _has(bind, T_CASE) and name not in have:
            op.add_column(T_CASE, col)
    if not _has(bind, T_APPEAL):
        op.create_table(
            T_APPEAL,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("case_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), index=True),
            sa.Column("reason", sa.String(length=1000)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="SUBMITTED", index=True),
            sa.Column("result", sa.String(length=30)),
            sa.Column("review_opinion", sa.String(length=1000)),
            sa.Column("reviewer", sa.String(length=100)),
            sa.Column("reviewed_at", sa.DateTime()),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    if _has(bind, T_APPEAL):
        op.drop_table(T_APPEAL)
    have = _cols(bind, T_CASE)
    for name in _NEW_COLS:
        if name in have:
            op.drop_column(T_CASE, name)
