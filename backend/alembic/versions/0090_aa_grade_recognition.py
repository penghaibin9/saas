"""成绩认定/课程替代表。

对标商业教务系统（强智《智慧教学服务平台操作手册》6-2 成绩认定管理，印刷页 399-401）：
转专业/转学学生将原修课程替换为现专业计划课程，审核通过写 t_acad_grade(source=RECOGNIZED)。

全新业务表；downgrade drop。幂等：inspect 判表。

Revision ID: 0090_aa_grade_recognition
Revises: 0089_aa_major_split
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0090_aa_grade_recognition"
down_revision = "0089_aa_major_split"
branch_labels = None
depends_on = None

TABLE = "t_aa_grade_recognition"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("student_no", sa.String(50)),
        sa.Column("student_name", sa.String(100)),
        sa.Column("source_course_name", sa.String(200), nullable=False),
        sa.Column("source_score", sa.Integer()),
        sa.Column("source_credit", sa.Numeric(4, 1)),
        sa.Column("source_origin", sa.String(300)),
        sa.Column("target_course_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("review_reason", sa.String(500)),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("acad_grade_id", sa.BigInteger()),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_aa_recog_student", TABLE, ["student_id"])
    op.create_index("ix_aa_recog_status", TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        op.drop_table(TABLE)
