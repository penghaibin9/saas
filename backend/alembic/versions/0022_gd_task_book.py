"""任务书 t_gd_task_book

Revision ID: 0022_gd_task_book
Revises: 0021_gd_mentor

导师下达→学生确认→变更需重确认的任务书业务闭环。幂等：inspect 已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0022_gd_task_book"
down_revision = "0021_gd_mentor"
branch_labels = None
depends_on = None

T = "t_gd_task_book"


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
        sa.Column("mentor_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("objective", sa.String(2000), nullable=True),
        sa.Column("content", sa.String(2000), nullable=True),
        sa.Column("progress_plan", sa.String(2000), nullable=True),
        sa.Column("outcome_requirement", sa.String(2000), nullable=True),
        sa.Column("taskbook_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING_CONFIRM"),
        sa.Column("history_json", sa.JSON(), nullable=True),
        sa.Column("issued_by", sa.String(100), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "gd_student_id", name="uk_gd_task_book_student"),
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
