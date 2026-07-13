"""13A-D 学生活动 波次3 党团建设：t_affairs_league_dev / t_affairs_league_dev_stage

Revision ID: 0057_13a_league_dev
Revises: 0056_13a_student_org
Create Date: 2026-07-14

党团发展阶段台账（一生一条）+ 阶段流转 append-only。材料仅存 file_id 脱敏。
幂等：表已存在则跳过。回滚：downgrade 逆序 drop（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0057_13a_league_dev"
down_revision = "0056_13a_student_org"
branch_labels = None
depends_on = None

T_DEV = "t_affairs_league_dev"
T_STAGE = "t_affairs_league_dev_stage"


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
    if not _has(bind, T_DEV):
        op.create_table(
            T_DEV,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("dev_type", sa.String(length=30), nullable=False, server_default="PARTY"),
            sa.Column("current_stage", sa.String(length=50), nullable=False, server_default="APPLICANT"),
            sa.Column("branch_name", sa.String(length=200)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ONGOING", index=True),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "student_id", "dev_type", name="uk_league_dev_student_type"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_STAGE):
        op.create_table(
            T_STAGE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("dev_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("from_stage", sa.String(length=50)),
            sa.Column("to_stage", sa.String(length=50), nullable=False),
            sa.Column("material_file_id", sa.BigInteger()),
            sa.Column("operator", sa.String(length=100)),
            sa.Column("remark", sa.String(length=1000)),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            *_common_cols(),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    for t in (T_STAGE, T_DEV):
        if _has(bind, t):
            op.drop_table(t)
