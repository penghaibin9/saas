"""助学贷款四端回执、退回与确认闭环。

Revision ID: 20260906_student_loan_four_end
Revises: 20260906_work_study_four_end
Create Date: 2026-09-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260906_student_loan_four_end"
down_revision = "20260906_work_study_four_end"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {str(column["name"]) for column in inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {str(index["name"]) for index in inspect(bind).get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    columns = _columns(bind, "t_affairs_student_loan")
    with op.batch_alter_table("t_affairs_student_loan") as batch:
        if "receipt_code_encrypted" not in columns:
            batch.add_column(sa.Column("receipt_code_encrypted", sa.String(500)))
        if "receipt_code_hash" not in columns:
            batch.add_column(sa.Column("receipt_code_hash", sa.String(64)))
        if "review_opinion" not in columns:
            batch.add_column(sa.Column("review_opinion", sa.String(1000)))
        if "reviewer" not in columns:
            batch.add_column(sa.Column("reviewer", sa.String(100)))
        for name in ("submitted_at", "returned_at", "verified_at", "confirmed_at", "withdrawn_at"):
            if name not in columns:
                batch.add_column(sa.Column(name, sa.DateTime()))
    if "ix_t_affairs_student_loan_receipt_code_hash" not in _indexes(bind, "t_affairs_student_loan"):
        op.create_index("ix_t_affairs_student_loan_receipt_code_hash", "t_affairs_student_loan", ["receipt_code_hash"])


def downgrade():
    bind = op.get_bind()
    columns = _columns(bind, "t_affairs_student_loan")
    indexes = _indexes(bind, "t_affairs_student_loan")
    if "ix_t_affairs_student_loan_receipt_code_hash" in indexes:
        op.drop_index("ix_t_affairs_student_loan_receipt_code_hash", table_name="t_affairs_student_loan")
    with op.batch_alter_table("t_affairs_student_loan") as batch:
        for name in (
            "withdrawn_at", "confirmed_at", "verified_at", "returned_at", "submitted_at",
            "reviewer", "review_opinion", "receipt_code_hash", "receipt_code_encrypted",
        ):
            if name in columns:
                batch.drop_column(name)
