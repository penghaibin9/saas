"""教务中心·注册管理 Tier1 六叶（入学/学年/资格核验/未注册/暂缓/异常）：

t_aa_registration 加 4 列（资格核验结果，独立于最终注册结果，不做硬阻断）；
新建 2 表：t_aa_registration_exception（注册异常）/ t_aa_registration_deferral（暂缓注册）。

Revision ID: aa_registration_tier1_r1
Revises: 0083_notification_preference
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_registration_tier1_r1"
down_revision = "0083_notification_preference"
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


def _has_column(bind, t, c):
    return c in [col["name"] for col in inspect(bind).get_columns(t)]


def upgrade() -> None:
    bind = op.get_bind()

    # ── t_aa_registration 加列：资格核验结果 ──
    if _has_table(bind, "t_aa_registration"):
        if not _has_column(bind, "t_aa_registration", "eligibility_status"):
            op.add_column("t_aa_registration", sa.Column(
                "eligibility_status", sa.String(20), nullable=False, server_default="PENDING"))
        if not _has_column(bind, "t_aa_registration", "eligibility_note"):
            op.add_column("t_aa_registration", sa.Column("eligibility_note", sa.String(500)))
        if not _has_column(bind, "t_aa_registration", "eligibility_checked_at"):
            op.add_column("t_aa_registration", sa.Column("eligibility_checked_at", sa.DateTime()))
        if not _has_column(bind, "t_aa_registration", "eligibility_checked_by"):
            op.add_column("t_aa_registration", sa.Column("eligibility_checked_by", sa.BigInteger()))

    # ── 注册异常 ──
    if not _has_table(bind, "t_aa_registration_exception"):
        op.create_table(
            "t_aa_registration_exception", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("registration_id", sa.BigInteger()),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("exception_type", sa.String(30), nullable=False, server_default="OTHER"),
            sa.Column("description", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
            sa.Column("resolution_note", sa.String(500)),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("resolved_by", sa.BigInteger()),
            *_COMMON)
        op.create_index("ix_aa_reg_exc_batch", "t_aa_registration_exception", ["tenant_id", "batch_id", "status"])
        op.create_index("ix_aa_reg_exc_student", "t_aa_registration_exception", ["tenant_id", "student_id"])

    # ── 暂缓注册 ──
    if not _has_table(bind, "t_aa_registration_deferral"):
        op.create_table(
            "t_aa_registration_deferral", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("requested_until", sa.DateTime()),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("review_note", sa.String(500)),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("reviewed_by", sa.BigInteger()),
            *_COMMON)
        op.create_index("ix_aa_reg_def_batch", "t_aa_registration_deferral", ["tenant_id", "batch_id", "status"])
        op.create_index("ix_aa_reg_def_student", "t_aa_registration_deferral", ["tenant_id", "student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_registration_deferral", "t_aa_registration_exception"):
        if _has_table(bind, t):
            op.drop_table(t)
    if _has_table(bind, "t_aa_registration"):
        for c in ("eligibility_checked_by", "eligibility_checked_at", "eligibility_note", "eligibility_status"):
            if _has_column(bind, "t_aa_registration", c):
                op.drop_column("t_aa_registration", c)
