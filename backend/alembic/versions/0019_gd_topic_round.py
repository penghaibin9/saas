"""毕设选题轮次与志愿 t_gd_topic_round / t_gd_topic_choice

Revision ID: 0019_gd_topic_round
Revises: 0018_gd_topic_lib
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0019_gd_topic_round"
down_revision = "0018_gd_topic_lib"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "t_gd_topic_round" not in insp.get_table_names():
        op.create_table(
            "t_gd_topic_round",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("round_name", sa.String(100), nullable=False),
            sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_choices", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
            sa.Column("start_at", sa.DateTime(), nullable=True),
            sa.Column("end_at", sa.DateTime(), nullable=True),
            sa.Column("college_scope", sa.String(200), nullable=True),
            sa.Column("remark", sa.String(500), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
        )
    if "t_gd_topic_choice" not in insp.get_table_names():
        op.create_table(
            "t_gd_topic_choice",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("round_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("gd_student_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("topic_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("choice_order", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(100), nullable=True),
            sa.Column("updated_by", sa.String(100), nullable=True),
            sa.UniqueConstraint("tenant_id", "round_id", "gd_student_id", "choice_order", name="uk_gd_topic_choice_order"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "t_gd_topic_choice" in insp.get_table_names():
        op.drop_table("t_gd_topic_choice")
    if "t_gd_topic_round" in insp.get_table_names():
        op.drop_table("t_gd_topic_round")
