"""等级考务：考试 + 报名两表。

对标商业教务系统（强智《智慧教学服务平台操作手册》5-2 等级考务，印刷页 327-344：
考级类别/等级/网上报名/缴费确认/成绩导入）。四六级/普通话/职业技能等级证书校内报名闭环。

全新业务表；downgrade drop。幂等：inspect 判表。

Revision ID: 0092_aa_level_exam
Revises: 0091_aa_graduation_certificate
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0092_aa_level_exam"
down_revision = "0091_aa_graduation_certificate"
branch_labels = None
depends_on = None


def _mixin():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    t = set(inspect(bind).get_table_names())
    if "t_aa_level_exam" not in t:
        op.create_table(
            "t_aa_level_exam",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("exam_name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(50), nullable=False, server_default="SKILL"),
            sa.Column("level", sa.String(50)),
            sa.Column("exam_date", sa.String(20)),
            sa.Column("fee", sa.Numeric(8, 2)),
            sa.Column("reg_start", sa.DateTime()),
            sa.Column("reg_end", sa.DateTime()),
            sa.Column("pass_line", sa.Integer()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            *_mixin(),
            sa.UniqueConstraint("tenant_id", "exam_name", name="uk_aa_level_exam"))
        op.create_index("ix_aa_level_exam_status", "t_aa_level_exam", ["status"])
    if "t_aa_level_exam_reg" not in t:
        op.create_table(
            "t_aa_level_exam_reg",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("exam_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("fee_status", sa.String(20), nullable=False, server_default="UNPAID"),
            sa.Column("score", sa.Integer()),
            sa.Column("result", sa.String(20)),
            sa.Column("cert_no", sa.String(100)),
            sa.Column("status", sa.String(20), nullable=False, server_default="REGISTERED"),
            *_mixin(),
            sa.UniqueConstraint("tenant_id", "exam_id", "student_id", name="uk_aa_level_reg"))
        op.create_index("ix_aa_level_reg_exam", "t_aa_level_exam_reg", ["exam_id"])
        op.create_index("ix_aa_level_reg_student", "t_aa_level_exam_reg", ["student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    t = set(inspect(bind).get_table_names())
    for name in ("t_aa_level_exam_reg", "t_aa_level_exam"):
        if name in t:
            op.drop_table(name)
