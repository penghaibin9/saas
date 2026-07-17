"""Bind internship advisor to a real user account.

Revision ID: 0048_internship_advisor_identity
Revises: 0047_internship_leave_return
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0048_internship_advisor_identity"
down_revision = "0047_internship_leave_return"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    return ({x["name"] for x in inspector.get_columns(table)}
            if table in inspector.get_table_names() else set())


def upgrade() -> None:
    bind = op.get_bind()
    _cols = _columns(bind, "t_internship_record")
    # 基表不存在时 _columns 返回空集；要求「表已存在」才 ALTER，避免对缺失表 add_column 崩溃
    # （全新库由 0053 基线迁移统一建全量结构）。
    if _cols and "advisor_user_id" not in _cols:
        op.add_column("t_internship_record", sa.Column("advisor_user_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_t_internship_record_advisor_user_id", "t_internship_record", ["advisor_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "advisor_user_id" in _columns(bind, "t_internship_record"):
        indexes = {x["name"] for x in inspect(bind).get_indexes("t_internship_record")}
        if "ix_t_internship_record_advisor_user_id" in indexes:
            op.drop_index("ix_t_internship_record_advisor_user_id", table_name="t_internship_record")
        op.drop_column("t_internship_record", "advisor_user_id")
