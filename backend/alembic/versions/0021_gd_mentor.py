"""毕设导师库 + 导师分配记录 t_gd_mentor / t_gd_mentor_assignment；t_gd_student 加 mentor_id

Revision ID: 0021_gd_mentor
Revises: 0020_gd_topic_change_request

导师管理 + 导师分配业务闭环：导师资格认证、容量、方向、工作量；分配/调导师历史留痕。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0021_gd_mentor"
down_revision = "0020_gd_topic_change_request"
branch_labels = None
depends_on = None

T_MENTOR = "t_gd_mentor"
T_ASSIGN = "t_gd_mentor_assignment"
T_STUDENT = "t_gd_student"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if T_MENTOR not in insp.get_table_names():
        op.create_table(
            T_MENTOR,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("teacher_no", sa.String(50), nullable=False, index=True),
            sa.Column("teacher_name", sa.String(100), nullable=False),
            sa.Column("mentor_type", sa.String(30), nullable=False, server_default="INTERNAL"),
            sa.Column("title", sa.String(50), nullable=True),
            sa.Column("college_id", sa.String(50), nullable=True),
            sa.Column("college_name", sa.String(100), nullable=True),
            sa.Column("major_name", sa.String(100), nullable=True),
            sa.Column("research_direction", sa.String(300), nullable=True),
            sa.Column("max_capacity", sa.Integer(), nullable=False, server_default="8"),
            sa.Column("current_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("phone_encrypted", sa.String(500), nullable=True),
            sa.Column("qualification_status", sa.String(50), nullable=False, server_default="PENDING_REVIEW"),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("reviewer_name", sa.String(100), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("disabled_reason", sa.String(500), nullable=True),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint("tenant_id", "teacher_no", name="uk_gd_mentor_teacher_no"),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index(f"ix_{T_MENTOR}_qualification_status", T_MENTOR, ["qualification_status"])

    if T_ASSIGN not in insp.get_table_names():
        op.create_table(
            T_ASSIGN,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("mentor_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("previous_mentor_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("assign_source", sa.String(30), nullable=False, server_default="MANUAL"),
            sa.Column("assign_reason", sa.String(500), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            sa.Column("confirmed_by_mentor", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("assigned_by", sa.String(100), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index(f"ix_{T_ASSIGN}_status", T_ASSIGN, ["status"])

    if T_STUDENT in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns(T_STUDENT)]
        if "mentor_id" not in cols:
            op.add_column(T_STUDENT, sa.Column("mentor_id", sa.BigInteger(), nullable=True))
            op.create_index(f"ix_{T_STUDENT}_mentor_id", T_STUDENT, ["mentor_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if T_STUDENT in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns(T_STUDENT)]
        if "mentor_id" in cols:
            op.drop_index(f"ix_{T_STUDENT}_mentor_id", table_name=T_STUDENT)
            op.drop_column(T_STUDENT, "mentor_id")
    for t in (T_ASSIGN, T_MENTOR):
        if t in insp.get_table_names():
            for idx in insp.get_indexes(t):
                op.drop_index(idx["name"], table_name=t)
            op.drop_table(t)
