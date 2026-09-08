"""勤工助学四端闭环所需岗位与协议字段。

Revision ID: 20260906_work_study_four_end
Revises: 20260901_orientation_self_activate_o6
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260906_work_study_four_end"
down_revision = "20260901_orientation_self_activate_o6"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {str(column["name"]) for column in inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    post_columns = _columns(bind, "t_affairs_work_study_post")
    record_columns = _columns(bind, "t_affairs_work_study_record")

    with op.batch_alter_table("t_affairs_work_study_post") as batch:
        if "employment_type" not in post_columns:
            batch.add_column(sa.Column("employment_type", sa.String(20), nullable=False, server_default="FIXED"))
        if "work_location" not in post_columns:
            batch.add_column(sa.Column("work_location", sa.String(200)))
        if "schedule_text" not in post_columns:
            batch.add_column(sa.Column("schedule_text", sa.String(500)))
        if "apply_end" not in post_columns:
            batch.add_column(sa.Column("apply_end", sa.DateTime()))
        if "monthly_hours_limit" not in post_columns:
            batch.add_column(sa.Column("monthly_hours_limit", sa.Numeric(6, 2), nullable=False, server_default="40.00"))
        if "agreement_required" not in post_columns:
            batch.add_column(sa.Column("agreement_required", sa.Boolean(), nullable=False, server_default=sa.text("1")))

    with op.batch_alter_table("t_affairs_work_study_record") as batch:
        if "apply_statement" not in record_columns:
            batch.add_column(sa.Column("apply_statement", sa.String(1000)))
        if "availability" not in record_columns:
            batch.add_column(sa.Column("availability", sa.String(500)))
        if "agreement_confirmed" not in record_columns:
            batch.add_column(sa.Column("agreement_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if "agreement_confirmed_at" not in record_columns:
            batch.add_column(sa.Column("agreement_confirmed_at", sa.DateTime()))


def downgrade():
    bind = op.get_bind()
    record_columns = _columns(bind, "t_affairs_work_study_record")
    post_columns = _columns(bind, "t_affairs_work_study_post")

    with op.batch_alter_table("t_affairs_work_study_record") as batch:
        for column in ("agreement_confirmed_at", "agreement_confirmed", "availability", "apply_statement"):
            if column in record_columns:
                batch.drop_column(column)

    with op.batch_alter_table("t_affairs_work_study_post") as batch:
        for column in ("agreement_required", "monthly_hours_limit", "apply_end", "schedule_text", "work_location", "employment_type"):
            if column in post_columns:
                batch.drop_column(column)
