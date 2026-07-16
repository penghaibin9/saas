"""专业分流：批次/可选专业/学生志愿三表。

对标商业教务系统（强智《智慧教学服务平台操作手册》7-5 专业分流，印刷页 481-495：
分流时间控制/学生志愿/分流编班/转出转入）。大类招生后按志愿+绩点分流是职校高频刚需。

全新业务表，无历史数据兼容问题；downgrade drop 三表。幂等：inspect 判表。

Revision ID: 0089_aa_major_split
Revises: 0088_aa_clearance_exam
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0089_aa_major_split"
down_revision = "0088_aa_clearance_exam"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _mixin_cols():
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
    t = _tables(bind)
    if "t_aa_major_split_batch" not in t:
        op.create_table(
            "t_aa_major_split_batch",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("grade", sa.String(20), nullable=False),
            sa.Column("source_major_id", sa.BigInteger()),
            sa.Column("max_choices", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("volunteer_start", sa.DateTime()),
            sa.Column("volunteer_end", sa.DateTime()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            *_mixin_cols(),
            sa.UniqueConstraint("tenant_id", "batch_name", name="uk_aa_major_split_batch"))
        op.create_index("ix_aa_split_batch_status", "t_aa_major_split_batch", ["status"])
    if "t_aa_major_split_option" not in t:
        op.create_table(
            "t_aa_major_split_option",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("major_id", sa.BigInteger(), nullable=False),
            sa.Column("major_name", sa.String(200)),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("allocated_count", sa.Integer(), nullable=False, server_default="0"),
            *_mixin_cols(),
            sa.UniqueConstraint("tenant_id", "batch_id", "major_id", name="uk_aa_split_option"))
        op.create_index("ix_aa_split_option_batch", "t_aa_major_split_option", ["batch_id"])
    if "t_aa_major_split_volunteer" not in t:
        op.create_table(
            "t_aa_major_split_volunteer",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("student_no", sa.String(50)),
            sa.Column("student_name", sa.String(100)),
            sa.Column("choices_json", sa.String(500)),
            sa.Column("gpa_snapshot", sa.Numeric(4, 2)),
            sa.Column("result_major_id", sa.BigInteger()),
            sa.Column("result_choice_rank", sa.Integer()),
            sa.Column("adjust_reason", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            *_mixin_cols(),
            sa.UniqueConstraint("tenant_id", "batch_id", "student_id", name="uk_aa_split_volunteer"))
        op.create_index("ix_aa_split_vol_batch", "t_aa_major_split_volunteer", ["batch_id"])
        op.create_index("ix_aa_split_vol_student", "t_aa_major_split_volunteer", ["student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    t = _tables(bind)
    for name in ("t_aa_major_split_volunteer", "t_aa_major_split_option", "t_aa_major_split_batch"):
        if name in t:
            op.drop_table(name)
