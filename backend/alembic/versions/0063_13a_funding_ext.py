"""13A 奖助扩展：勤工岗位/记录 + 助学贷款 + 减免临补（4 表）

Revision ID: 0063_13a_funding_ext
Revises: 0062_13a_counselor_eval
Create Date: 2026-07-14

V1 冻结解除后补建。四表新增。幂等：表已存在则跳过。回滚：逆序 drop。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0063_13a_funding_ext"
down_revision = "0062_13a_counselor_eval"
branch_labels = None
depends_on = None

T_POST = "t_affairs_work_study_post"
T_REC = "t_affairs_work_study_record"
T_LOAN = "t_affairs_student_loan"
T_FEE = "t_affairs_fee_reduction"


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
    if not _has(bind, T_POST):
        op.create_table(
            T_POST,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("dept_name", sa.String(length=200), nullable=False),
            sa.Column("post_name", sa.String(length=200), nullable=False),
            sa.Column("salary", sa.Numeric(precision=10, scale=2)),
            sa.Column("headcount", sa.Integer()),
            sa.Column("requirement", sa.String(length=1000)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ENABLED", index=True),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_REC):
        op.create_table(
            T_REC,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("post_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="APPLIED", index=True),
            sa.Column("onboard_at", sa.DateTime()),
            sa.Column("terminated_at", sa.DateTime()),
            sa.Column("subsidy_total", sa.Numeric(precision=12, scale=2), server_default="0"),
            sa.Column("remark", sa.String(length=500)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "post_id", "student_id", "status", name="uk_work_study_active"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_LOAN):
        op.create_table(
            T_LOAN,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("loan_type", sa.String(length=30), nullable=False, server_default="ORIGIN"),
            sa.Column("bank_name", sa.String(length=200)),
            sa.Column("bank_last4", sa.String(length=10)),
            sa.Column("year_code", sa.String(length=50)),
            sa.Column("amount", sa.Numeric(precision=12, scale=2)),
            sa.Column("receipt_file_id", sa.BigInteger()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="REGISTERED", index=True),
            sa.Column("remark", sa.String(length=500)),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_FEE):
        op.create_table(
            T_FEE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("item_type", sa.String(length=30), nullable=False, server_default="REDUCTION"),
            sa.Column("amount", sa.Numeric(precision=12, scale=2)),
            sa.Column("reason", sa.String(length=1000)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="SUBMITTED", index=True),
            sa.Column("review_opinion", sa.String(length=1000)),
            sa.Column("reviewer", sa.String(length=100)),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("issued_at", sa.DateTime()),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    for t in (T_FEE, T_LOAN, T_REC, T_POST):
        if _has(bind, t):
            op.drop_table(t)
