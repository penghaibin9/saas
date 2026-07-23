"""毕设学生台账补学院/专业 ID，供学院/专业管理员 claim 收敛。

Revision ID: 0116_gd_student_org_scope
Revises: 0114_appeal_open_key
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0116_gd_student_org_scope"
down_revision = "0114_appeal_open_key"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "t_gd_student")
    if not cols:
        return
    if "college_id" not in cols:
        op.add_column("t_gd_student", sa.Column("college_id", sa.String(50), nullable=True,
                                                comment="学院ID（组织范围 claim 对齐）"))
    if "major_id" not in cols:
        op.add_column("t_gd_student", sa.Column("major_id", sa.String(50), nullable=True,
                                                comment="专业ID（组织范围 claim 对齐）"))
    idxs = _indexes(bind, "t_gd_student")
    if "ix_t_gd_student_college_id" not in idxs:
        op.create_index("ix_t_gd_student_college_id", "t_gd_student", ["college_id"])
    if "ix_t_gd_student_major_id" not in idxs:
        op.create_index("ix_t_gd_student_major_id", "t_gd_student", ["major_id"])


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "t_gd_student")
    if not cols:
        return
    idxs = _indexes(bind, "t_gd_student")
    if "ix_t_gd_student_major_id" in idxs:
        op.drop_index("ix_t_gd_student_major_id", table_name="t_gd_student")
    if "ix_t_gd_student_college_id" in idxs:
        op.drop_index("ix_t_gd_student_college_id", table_name="t_gd_student")
    if "major_id" in cols:
        op.drop_column("t_gd_student", "major_id")
    if "college_id" in cols:
        op.drop_column("t_gd_student", "college_id")
