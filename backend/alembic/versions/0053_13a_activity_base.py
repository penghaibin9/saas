"""13A-D 学生活动与第二课堂 波次1 活动底座：
t_affairs_activity / t_affairs_activity_signup / t_affairs_activity_credit / t_affairs_credit_category

Revision ID: 0053_13a_activity_base
Revises: 0052_internship_p4_loops
Create Date: 2026-07-14

依据中青联发〔2018〕5号《第二课堂成绩单制度》（已核验原文）。四表均新增（全域此前 missing）。
幂等：表已存在则跳过。回滚：downgrade 逆序 drop 本波四表（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0053_13a_activity_base"
down_revision = "0052_internship_p4_loops"
branch_labels = None
depends_on = None

T_ACT = "t_affairs_activity"
T_SIGNUP = "t_affairs_activity_signup"
T_CREDIT = "t_affairs_activity_credit"
T_CAT = "t_affairs_credit_category"


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


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, T_ACT):
        op.create_table(
            T_ACT,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("activity_name", sa.String(length=200), nullable=False),
            sa.Column("activity_type", sa.String(length=30), nullable=False, server_default="ACTIVITY", index=True),
            sa.Column("scope_type", sa.String(length=30)),
            sa.Column("scope_ref", sa.String(length=100)),
            sa.Column("org_id", sa.BigInteger(), index=True),
            sa.Column("location", sa.String(length=200)),
            sa.Column("description", sa.String(length=2000)),
            sa.Column("start_at", sa.DateTime(), index=True),
            sa.Column("end_at", sa.DateTime()),
            sa.Column("enroll_deadline", sa.DateTime()),
            sa.Column("quota", sa.Integer()),
            sa.Column("credit_type", sa.String(length=30)),
            sa.Column("credit_value", sa.Numeric(precision=6, scale=2)),
            sa.Column("category_code", sa.String(length=50)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT", index=True),
            sa.Column("publisher_id", sa.BigInteger(), index=True),
            sa.Column("publisher_name", sa.String(length=100)),
            sa.Column("confirm_at", sa.DateTime()),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_activity_tenant_type_status_start", T_ACT,
                        ["tenant_id", "activity_type", "status", "start_at"])

    if not _has(bind, T_SIGNUP):
        op.create_table(
            T_SIGNUP,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("activity_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("signup_status", sa.String(length=30), nullable=False, server_default="ENROLLED"),
            sa.Column("enrolled_at", sa.DateTime()),
            sa.Column("checkin_at", sa.DateTime()),
            sa.Column("checkin_method", sa.String(length=30)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "activity_id", "student_id", name="uk_activity_signup"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )

    if not _has(bind, T_CREDIT):
        op.create_table(
            T_CREDIT,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("activity_id", sa.BigInteger(), index=True),
            sa.Column("credit_type", sa.String(length=30), nullable=False, server_default="SECOND_CLASS"),
            sa.Column("credit_value", sa.Numeric(precision=6, scale=2), nullable=False, server_default="0"),
            sa.Column("category_code", sa.String(length=50), index=True),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="ACTIVITY"),
            sa.Column("remark", sa.String(length=500)),
            sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            # append-only（AuditTimeMixin）：仅 created_at/created_by
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.UniqueConstraint("tenant_id", "student_id", "activity_id", "credit_type", name="uk_activity_credit"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )

    if not _has(bind, T_CAT):
        op.create_table(
            T_CAT,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("category_code", sa.String(length=50), nullable=False),
            sa.Column("category_name", sa.String(length=100), nullable=False),
            sa.Column("credit_type", sa.String(length=30)),
            sa.Column("description", sa.String(length=500)),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ENABLED"),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "category_code", name="uk_credit_category"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade() -> None:
    bind = op.get_bind()
    for t in (T_CAT, T_CREDIT, T_SIGNUP, T_ACT):
        if _has(bind, t):
            op.drop_table(t)
