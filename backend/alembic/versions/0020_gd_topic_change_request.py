"""毕设选题变更申请 t_gd_topic_change_request

Revision ID: 0020_gd_topic_change_request
Revises: 0019_gd_topic_round

获批题目已有学生后换题的独立变更申请流程（提交→教师/管理员重新审核→通过后生效）。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0020_gd_topic_change_request"
down_revision = "0019_gd_topic_round"
branch_labels = None
depends_on = None

T = "t_gd_topic_change_request"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if T in insp.get_table_names():
        return
    op.create_table(
        T,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("old_topic_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("new_topic_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("requested_by", sa.String(100), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(f"ix_{T}_status", T, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if T in insp.get_table_names():
        for idx in insp.get_indexes(T):
            op.drop_index(idx["name"], table_name=T)
        op.drop_table(T)
