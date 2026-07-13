"""13A-D 学生活动 波次3 社团管理：t_affairs_club / t_affairs_club_member / t_affairs_club_annual_review

Revision ID: 0055_13a_club
Revises: 0054_13a_volunteer_record
Create Date: 2026-07-14

三表均新增（全域此前 missing）。幂等：表已存在则跳过。回滚：downgrade 逆序 drop（无历史数据零风险）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0055_13a_club"
down_revision = "0054_13a_volunteer_record"
branch_labels = None
depends_on = None

T_CLUB = "t_affairs_club"
T_MEMBER = "t_affairs_club_member"
T_REVIEW = "t_affairs_club_annual_review"


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
    if not _has(bind, T_CLUB):
        op.create_table(
            T_CLUB,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("club_name", sa.String(length=200), nullable=False),
            sa.Column("club_type", sa.String(length=50), nullable=False, server_default="INTEREST"),
            sa.Column("college_id", sa.BigInteger(), index=True),
            sa.Column("advisor_name", sa.String(length=100)),
            sa.Column("president_student_id", sa.BigInteger(), index=True),
            sa.Column("founder_student_id", sa.BigInteger()),
            sa.Column("charter_file_id", sa.BigInteger()),
            sa.Column("member_count", sa.Integer(), server_default="0"),
            sa.Column("established_at", sa.DateTime()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING", index=True),
            sa.Column("reject_reason", sa.String(length=500)),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "club_name", name="uk_club_name"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_MEMBER):
        op.create_table(
            T_MEMBER,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("club_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("role", sa.String(length=50), nullable=False, server_default="MEMBER"),
            sa.Column("joined_at", sa.DateTime()),
            sa.Column("quit_at", sa.DateTime()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE", index=True),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "club_id", "student_id", "status", name="uk_club_member_active"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
    if not _has(bind, T_REVIEW):
        op.create_table(
            T_REVIEW,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("club_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("review_year", sa.String(length=20), nullable=False),
            sa.Column("result", sa.String(length=30), nullable=False, server_default="PASS"),
            sa.Column("activity_count", sa.Integer()),
            sa.Column("material_file_id", sa.BigInteger()),
            sa.Column("comment", sa.String(length=1000)),
            sa.Column("reviewer_name", sa.String(length=100)),
            sa.Column("reviewed_at", sa.DateTime()),
            *_common_cols(),
            sa.UniqueConstraint("tenant_id", "club_id", "review_year", name="uk_club_annual_review"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )


def downgrade():
    bind = op.get_bind()
    for t in (T_REVIEW, T_MEMBER, T_CLUB):
        if _has(bind, t):
            op.drop_table(t)
