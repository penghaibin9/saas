"""13B 教材费用部分收款：t_aa_textbook_fee_ledger 加列 paid_amount。

支持 PARTIAL 部分收款（已收金额 < 应收）。nullable/带默认，历史行零回填。幂等：inspect 判列。

Revision ID: 0079_13b_textbook_fee_partial
Revises: 0078_13b_archive
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0079_13b_textbook_fee_partial"
down_revision = "0078_13b_archive"
branch_labels = None
depends_on = None

TABLE = "t_aa_textbook_fee_ledger"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names() and "paid_amount" not in _cols(bind):
        op.add_column(TABLE, sa.Column("paid_amount", sa.Numeric(8, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    if "paid_amount" in _cols(bind):
        op.drop_column(TABLE, "paid_amount")
