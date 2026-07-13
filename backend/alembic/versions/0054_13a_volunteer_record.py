"""13A-D 学生活动 波次2 志愿服务：t_affairs_volunteer_record（校外/线下志愿时长补录认定）

Revision ID: 0054_13a_volunteer_record
Revises: 0053_13a_activity_base
Create Date: 2026-07-14

依据中青联发〔2018〕5号《第二课堂成绩单制度》志愿公益体系（已核验原文）。
新增单表；确认后写 t_affairs_activity_credit(VOLUNTEER_HOUR, source=VOLUNTEER_RECORD)，复用波次1 学分账。
幂等：表已存在则跳过。回滚：downgrade drop 本表（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0054_13a_volunteer_record"
down_revision = "0053_13a_activity_base"
branch_labels = None
depends_on = None

T_VOL = "t_affairs_volunteer_record"


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
    if not _has(bind, T_VOL):
        op.create_table(
            T_VOL,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("activity_id", sa.BigInteger(), index=True),
            sa.Column("service_name", sa.String(length=200), nullable=False),
            sa.Column("org_name", sa.String(length=200)),
            sa.Column("hours", sa.Numeric(precision=6, scale=2), nullable=False, server_default="0"),
            sa.Column("service_date", sa.DateTime()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING", index=True),
            sa.Column("credit_id", sa.BigInteger()),
            sa.Column("reject_reason", sa.String(length=500)),
            sa.Column("remark", sa.String(length=500)),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_volunteer_tenant_student", T_VOL, ["tenant_id", "student_id"])


def downgrade():
    bind = op.get_bind()
    if _has(bind, T_VOL):
        op.drop_table(T_VOL)
