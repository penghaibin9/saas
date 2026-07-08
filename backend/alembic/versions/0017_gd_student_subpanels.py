"""毕设学生三级子模块字段：资格/分组/答辩组/毕业资格联动

Revision ID: 0017_gd_student_subpanels
Revises: 0016_internship_agreement_template
Create Date: 2026-07-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0017_gd_student_subpanels"
down_revision = "0016_internship_agreement_template"
branch_labels = None
depends_on = None

T = "t_gd_student"


def _has_col(bind, table, col):
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if T not in inspect(bind).get_table_names():
        return
    if not _has_col(bind, T, "defense_group_id"):
        op.add_column(T, sa.Column("defense_group_id", sa.BigInteger(), nullable=True, comment="答辩组 id"))
        op.create_index("ix_t_gd_student_defense_group_id", T, ["defense_group_id"])
    if not _has_col(bind, T, "eligibility_status"):
        op.add_column(T, sa.Column("eligibility_status", sa.String(50), nullable=False, server_default="PENDING"))
    if not _has_col(bind, T, "student_group"):
        op.add_column(T, sa.Column("student_group", sa.String(100), nullable=True))
    if not _has_col(bind, T, "grad_qual_status"):
        op.add_column(T, sa.Column("grad_qual_status", sa.String(50), nullable=False, server_default="UNKNOWN"))
    if not _has_col(bind, T, "grad_qual_note"):
        op.add_column(T, sa.Column("grad_qual_note", sa.String(500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if T not in inspect(bind).get_table_names():
        return
    for col in ("grad_qual_note", "grad_qual_status", "student_group", "eligibility_status"):
        if _has_col(bind, T, col):
            op.drop_column(T, col)
    if _has_col(bind, T, "defense_group_id"):
        op.drop_index("ix_t_gd_student_defense_group_id", table_name=T)
        op.drop_column(T, "defense_group_id")
