"""教师工作量申报表（对标正方 教师端1.18教学工作量申报/1.19考试工作量申报）。

教师申报教学/监考/阅卷/出卷/其他 课时 → 教务审核(通过/驳回)，通过后计入教务侧工作量统计「申报工时」。
正式薪酬核算(职称/系数)属人事系统，不在此实现。

全新业务表；downgrade drop。幂等：inspect 判表。

Revision ID: 0098_aa_workload_declaration
Revises: 0097_aa_eval_multisource
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0098_aa_workload_declaration"
down_revision = "0097_aa_eval_multisource"
branch_labels = None
depends_on = None

TABLE = "t_aa_workload_declaration"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("teacher_key", sa.String(100), nullable=False),
        sa.Column("teacher_name", sa.String(100)),
        sa.Column("term_code", sa.String(50)),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("hours", sa.Numeric(6, 1), nullable=False, server_default="0"),
        sa.Column("description", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"),
        sa.Column("review_note", sa.String(500)),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_aa_workload_teacher", TABLE, ["teacher_key"])
    op.create_index("ix_aa_workload_status", TABLE, ["status"])
    op.create_index("ix_aa_workload_term", TABLE, ["term_code"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in inspect(bind).get_table_names():
        op.drop_table(TABLE)
