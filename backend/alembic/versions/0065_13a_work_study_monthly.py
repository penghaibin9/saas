"""13A 勤工月度考核：t_affairs_work_study_monthly

Revision ID: 0065_13a_work_study_monthly
Revises: 0064_13a_family_receipt
Create Date: 2026-07-14

单表新增；月度考核确认累计补贴到上岗记录 subsidy_total。幂等：表已存在则跳过。回滚：drop。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0065_13a_work_study_monthly"
down_revision = "0064_13a_family_receipt"
branch_labels = None
depends_on = None

T = "t_affairs_work_study_monthly"


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


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
    if not _has(bind, T):
        op.create_table(
            T,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("record_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("month_code", sa.String(length=20), nullable=False),
            sa.Column("work_hours", sa.Numeric(precision=6, scale=2)),
            sa.Column("rating", sa.String(length=20), nullable=False, server_default="PASS"),
            sa.Column("subsidy_amount", sa.Numeric(precision=10, scale=2)),
            sa.Column("remark", sa.String(length=500)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "record_id", "month_code", name="uk_work_study_monthly"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    if _has(bind, T):
        op.drop_table(T)
