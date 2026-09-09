"""减免与临时补助四端申请、补正和结果落实闭环。

Revision ID: 20260906_fee_reduction_four_end
Revises: 20260906_student_loan_four_end
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260906_fee_reduction_four_end"
down_revision = "20260906_student_loan_four_end"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {str(column["name"]) for column in inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {str(index["name"]) for index in inspect(bind).get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    columns = _columns(bind, "t_affairs_fee_reduction")
    with op.batch_alter_table("t_affairs_fee_reduction") as batch:
        for name, column in (
            ("year_code", sa.Column("year_code", sa.String(20))),
            ("reason_category", sa.Column("reason_category", sa.String(50))),
            ("fulfillment_channel", sa.Column("fulfillment_channel", sa.String(30))),
            ("fulfillment_reference", sa.Column("fulfillment_reference", sa.String(200))),
            ("submitted_at", sa.Column("submitted_at", sa.DateTime())),
            ("returned_at", sa.Column("returned_at", sa.DateTime())),
            ("withdrawn_at", sa.Column("withdrawn_at", sa.DateTime())),
        ):
            if name not in columns:
                batch.add_column(column)
    if "ix_t_affairs_fee_reduction_year_code" not in _indexes(bind, "t_affairs_fee_reduction"):
        op.create_index("ix_t_affairs_fee_reduction_year_code", "t_affairs_fee_reduction", ["year_code"])


def downgrade():
    bind = op.get_bind()
    columns = _columns(bind, "t_affairs_fee_reduction")
    if "ix_t_affairs_fee_reduction_year_code" in _indexes(bind, "t_affairs_fee_reduction"):
        op.drop_index("ix_t_affairs_fee_reduction_year_code", table_name="t_affairs_fee_reduction")
    with op.batch_alter_table("t_affairs_fee_reduction") as batch:
        for name in (
            "withdrawn_at", "returned_at", "submitted_at", "fulfillment_reference",
            "fulfillment_channel", "reason_category", "year_code",
        ):
            if name in columns:
                batch.drop_column(name)
