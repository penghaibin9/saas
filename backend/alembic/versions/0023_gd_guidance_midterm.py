"""指导过程记录 + 中期检查 t_gd_guidance / t_gd_midterm

Revision ID: 0023_gd_guidance_midterm
Revises: 0022_gd_task_book

指导过程时间线留痕（指导频次统计/不足预警）+ 中期检查三档结论与整改跟踪闭环。
幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0023_gd_guidance_midterm"
down_revision = "0022_gd_task_book"
branch_labels = None
depends_on = None

T_GUIDANCE = "t_gd_guidance"
T_MIDTERM = "t_gd_midterm"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if T_GUIDANCE not in insp.get_table_names():
        op.create_table(
            T_GUIDANCE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("mentor_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("guidance_date", sa.DateTime(), nullable=True),
            sa.Column("method", sa.String(30), nullable=False, server_default="ONLINE"),
            sa.Column("content", sa.String(2000), nullable=True),
            sa.Column("issues", sa.String(1000), nullable=True),
            sa.Column("attachments_json", sa.JSON(), nullable=True),
            sa.Column("void_reason", sa.String(500), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )

    if T_MIDTERM not in insp.get_table_names():
        op.create_table(
            T_MIDTERM,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("conclusion", sa.String(30), nullable=True),
            sa.Column("check_comment", sa.String(1000), nullable=True),
            sa.Column("check_by", sa.String(100), nullable=True),
            sa.Column("checked_at", sa.DateTime(), nullable=True),
            sa.Column("rectify_deadline", sa.DateTime(), nullable=True),
            sa.Column("rectify_content", sa.String(2000), nullable=True),
            sa.Column("rectify_submitted_at", sa.DateTime(), nullable=True),
            sa.Column("rectify_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("review_comment", sa.String(1000), nullable=True),
            sa.Column("reviewed_by", sa.String(100), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_midterm_student"),
            mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index(f"ix_{T_MIDTERM}_status", T_MIDTERM, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for t in (T_MIDTERM, T_GUIDANCE):
        if t in insp.get_table_names():
            for idx in insp.get_indexes(t):
                op.drop_index(idx["name"], table_name=t)
            op.drop_table(t)
