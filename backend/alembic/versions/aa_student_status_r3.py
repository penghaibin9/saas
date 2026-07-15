"""教务中心·学籍管理 Tier1 R3（休学/复学/退学/转专业/保留学籍分类视图 + 学籍信息更正 + 学籍统计/归档轻量入口）：

新建 1 表：t_aa_student_correction（学籍信息更正申请，单步审核，PENDING/APPROVED/REJECTED）。
休学/复学/退学/转专业/保留学籍分类视图、学籍统计、学籍归档均为既有 roster/status-changes/stats/archive
端点的只读复用，不新增表结构。

Revision ID: aa_student_status_r3
Revises: aa_course_lib_tier1_r2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_student_status_r3"
down_revision = "aa_course_lib_tier1_r2"
branch_labels = None
depends_on = None

_COMMON = [
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    sa.Column("created_by", sa.BigInteger()),
    sa.Column("updated_by", sa.BigInteger()),
    sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
]


def _pk_tenant():
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
    ]


def _has_table(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "t_aa_student_correction"):
        op.create_table(
            "t_aa_student_correction", *_pk_tenant(),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("field_key", sa.String(30), nullable=False,
                     comment="STUDENT_NO/REAL_NAME/GENDER/ID_CARD/GRADE"),
            sa.Column("old_value", sa.String(500)),
            sa.Column("new_value", sa.String(500), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("review_note", sa.String(500)),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("reviewed_by", sa.BigInteger()),
            *_COMMON)
        op.create_index("ix_aa_student_correction_student", "t_aa_student_correction",
                        ["tenant_id", "student_id", "status"])
        op.create_index("ix_aa_student_correction_status", "t_aa_student_correction",
                        ["tenant_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "t_aa_student_correction"):
        op.drop_table("t_aa_student_correction")
