"""13B-SM-07 排课管理：建 2 表（排课规则中心 + 教师可用时间），复用既有课表批次/条目。

t_aa_schedule_rule    排课规则中心
t_aa_teacher_availability 教师可用时间（PENDING/ADOPTED/REJECTED）

全新业务表，无存量兼容负担；downgrade 逆序 drop。幂等：inspect 判表存在再建/删。

Revision ID: 0076_13b_scheduling
Revises: 0075_13b_textbook
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0076_13b_scheduling"
down_revision = "0075_13b_textbook"
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


def _has(bind, t):
    return t in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_schedule_rule"):
        op.create_table(
            "t_aa_schedule_rule", *_pk_tenant(),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("batch_id", sa.BigInteger()),
            sa.Column("rule_key", sa.String(100), nullable=False),
            sa.Column("rule_value_json", sa.String(2000)),
            sa.Column("remark", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="ENABLED"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "term_id", "batch_id", "rule_key", name="uk_aa_sched_rule"))
        op.create_index("ix_aa_sched_rule_key", "t_aa_schedule_rule", ["tenant_id", "rule_key"])

    if not _has(bind, "t_aa_teacher_availability"):
        op.create_table(
            "t_aa_teacher_availability", *_pk_tenant(),
            sa.Column("teacher_key", sa.String(100), nullable=False),
            sa.Column("teacher_name", sa.String(100)),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("slot_no", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(300)),
            sa.Column("review_reason", sa.String(300)),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "teacher_key", "term_id", "weekday", "slot_no",
                                name="uk_aa_teacher_avail"))
        op.create_index("ix_aa_teacher_avail", "t_aa_teacher_availability", ["tenant_id", "teacher_key", "term_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_teacher_availability", "t_aa_schedule_rule"):
        if _has(bind, t):
            op.drop_table(t)
