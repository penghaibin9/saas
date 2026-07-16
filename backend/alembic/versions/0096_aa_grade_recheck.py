"""成绩复查申请表（学生对已发布成绩发起复查）。

对标正方《教学管理信息服务平台》学生端 3.12 成绩复查申请 / 教师端 3.11 成绩复查审核：
学生对本人某门已发布成绩发起复查 → 教务复审 维持(UPHELD)/调整(ADJUSTED，回写 t_acad_grade
source=RECHECK + 刷新台账 + 通知学生)/不予受理(REJECTED)。

全新业务表；downgrade drop。幂等：inspect 判表。

Revision ID: 0096_aa_grade_recheck
Revises: 0095_aa_attendance_type
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0096_aa_grade_recheck"
down_revision = "0095_aa_attendance_type"
branch_labels = None
depends_on = None

TABLE = "t_aa_grade_recheck"


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
        sa.Column("acad_grade_id", sa.BigInteger(), nullable=False),
        sa.Column("course_name", sa.String(200)),
        sa.Column("term", sa.String(50)),
        sa.Column("original_score", sa.Integer()),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
        sa.Column("new_score", sa.Integer()),
        sa.Column("review_note", sa.String(500)),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_aa_recheck_student", TABLE, ["student_id"])
    op.create_index("ix_aa_recheck_grade", TABLE, ["acad_grade_id"])
    op.create_index("ix_aa_recheck_status", TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        op.drop_table(TABLE)
