"""补全 0037 过程报告/变更申请表 created_by 字段

Revision ID: 0040_internship_0037_created_by
Revises: 0039_internship_plan_created_by
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0040_internship_0037_created_by"
down_revision = "0039_internship_plan_created_by"
branch_labels = None
depends_on = None


def _cols(bind, t):
    if t not in inspect(bind).get_table_names():
        return set()
    return {c["name"] for c in inspect(bind).get_columns(t)}


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("t_internship_process_report", "t_internship_change_request"):
        cols = _cols(bind, table)
        if cols and "created_by" not in cols:
            op.add_column(table, sa.Column("created_by", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("t_internship_process_report", "t_internship_change_request"):
        cols = _cols(bind, table)
        if "created_by" in cols:
            op.drop_column(table, "created_by")
