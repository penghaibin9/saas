"""13A-D 学生活动 波次3 学生干部与组织：t_affairs_student_org / t_affairs_org_position

Revision ID: 0056_13a_student_org
Revises: 0055_13a_club
Create Date: 2026-07-14

两表均新增。班级班干部复用既有 t_affairs_class_cadre，不在此迁移。
幂等：表已存在则跳过。回滚：downgrade 逆序 drop（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0056_13a_student_org"
down_revision = "0055_13a_club"
branch_labels = None
depends_on = None

T_ORG = "t_affairs_student_org"
T_POS = "t_affairs_org_position"


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
    if not _has(bind, T_ORG):
        op.create_table(
            T_ORG,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("org_name", sa.String(length=200), nullable=False),
            sa.Column("org_type", sa.String(length=50), nullable=False, server_default="STUDENT_UNION"),
            sa.Column("level", sa.String(length=30), nullable=False, server_default="SCHOOL"),
            sa.Column("college_id", sa.BigInteger(), index=True),
            sa.Column("advisor_name", sa.String(length=100)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE", index=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "org_name", name="uk_student_org_name"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_POS):
        op.create_table(
            T_POS,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("org_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("position", sa.String(length=100), nullable=False),
            sa.Column("term_code", sa.String(length=50)),
            sa.Column("appointed_at", sa.DateTime()),
            sa.Column("removed_at", sa.DateTime()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE", index=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "org_id", "student_id", "position", "status",
                                name="uk_org_position_active"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    for t in (T_POS, T_ORG):
        if _has(bind, t):
            op.drop_table(t)
