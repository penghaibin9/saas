"""13A-C 家校回执：t_affairs_family_contact_log 加回执列

Revision ID: 0064_13a_family_receipt
Revises: 0063_13a_funding_ext
Create Date: 2026-07-14

加列不改旧列（receipt_status/receipt_at/receipt_note），旧行 receipt_status 默认 PENDING。
幂等：列已存在则跳过。回滚：drop 列。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0064_13a_family_receipt"
down_revision = "0063_13a_funding_ext"
branch_labels = None
depends_on = None

T = "t_affairs_family_contact_log"
_COLS = {
    "receipt_status": sa.Column("receipt_status", sa.String(length=20), nullable=False, server_default="PENDING"),
    "receipt_at": sa.Column("receipt_at", sa.DateTime()),
    "receipt_note": sa.Column("receipt_note", sa.String(length=500)),
}


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def _cols(bind):
    return {c["name"] for c in inspect(bind).get_columns(T)} if _has(bind, T) else set()


def upgrade():
    bind = op.get_bind()
    have = _cols(bind)
    for name, col in _COLS.items():
        if _has(bind, T) and name not in have:
            op.add_column(T, col)


def downgrade():
    bind = op.get_bind()
    have = _cols(bind)
    for name in _COLS:
        if name in have:
            op.drop_column(T, name)
