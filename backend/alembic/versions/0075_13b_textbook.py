"""13B 教材管理：建 9 表（目录/选用/审核批次+item/征订批次+明细/发放批次+明细/费用台账）。

全新业务表，无存量兼容负担；downgrade 逆序 drop。幂等：inspect 判表存在再建/删。

Revision ID: 0075_13b_textbook
Revises: 0074_13b_makeup
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0075_13b_textbook"
down_revision = "0074_13b_makeup"
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

    if not _has(bind, "t_aa_textbook"):
        op.create_table(
            "t_aa_textbook", *_pk_tenant(),
            sa.Column("name", sa.String(300), nullable=False),
            sa.Column("isbn", sa.String(30)),
            sa.Column("publisher", sa.String(200)),
            sa.Column("edition", sa.String(50)),
            sa.Column("author", sa.String(200)),
            sa.Column("subject", sa.String(100)),
            sa.Column("unit_price", sa.Numeric(8, 2)),
            sa.Column("is_national_standard", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.String(20), nullable=False, server_default="ENABLED"),
            *_COMMON)
        op.create_index("ix_aa_textbook_isbn", "t_aa_textbook", ["tenant_id", "isbn"])

    if not _has(bind, "t_aa_textbook_selection"):
        op.create_table(
            "t_aa_textbook_selection", *_pk_tenant(),
            sa.Column("task_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_name", sa.String(300)),
            sa.Column("course_name", sa.String(200)),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("officer_teacher_id", sa.BigInteger()),
            sa.Column("officer_key", sa.String(100)),
            sa.Column("expected_qty", sa.Integer()),
            sa.Column("remark", sa.String(500)),
            sa.Column("reject_reason", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            *_COMMON)
        op.create_index("ix_aa_tb_sel_task", "t_aa_textbook_selection", ["tenant_id", "task_id", "status"])

    if not _has(bind, "t_aa_textbook_review_batch"):
        op.create_table(
            "t_aa_textbook_review_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("publicity_start_at", sa.DateTime()),
            sa.Column("publicity_end_at", sa.DateTime()),
            sa.Column("college_reviewer", sa.String(100)),
            sa.Column("academic_reviewer", sa.String(100)),
            sa.Column("reject_reason", sa.String(500)),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON)

    if not _has(bind, "t_aa_textbook_review_batch_item"):
        op.create_table(
            "t_aa_textbook_review_batch_item", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("selection_id", sa.BigInteger(), nullable=False),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "batch_id", "selection_id", name="uk_aa_tb_review_item"))

    if not _has(bind, "t_aa_textbook_order_batch"):
        op.create_table(
            "t_aa_textbook_order_batch", *_pk_tenant(),
            sa.Column("batch_name", sa.String(200), nullable=False),
            sa.Column("term_id", sa.BigInteger()),
            sa.Column("college_id", sa.BigInteger()),
            sa.Column("submit_at", sa.DateTime()),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            *_COMMON)

    if not _has(bind, "t_aa_textbook_order_item"):
        op.create_table(
            "t_aa_textbook_order_item", *_pk_tenant(),
            sa.Column("order_batch_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_name", sa.String(300)),
            sa.Column("order_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("arrived_qty", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_price_snapshot", sa.Numeric(8, 2)),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "order_batch_id", "textbook_id", name="uk_aa_tb_order_item"))

    if not _has(bind, "t_aa_textbook_distribution_batch"):
        op.create_table(
            "t_aa_textbook_distribution_batch", *_pk_tenant(),
            sa.Column("order_batch_id", sa.BigInteger(), nullable=False),
            sa.Column("class_id", sa.BigInteger()),
            sa.Column("class_name", sa.String(100)),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "order_batch_id", "class_id", name="uk_aa_tb_dist_batch"))

    if not _has(bind, "t_aa_textbook_distribution_record"):
        op.create_table(
            "t_aa_textbook_distribution_record", *_pk_tenant(),
            sa.Column("batch_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_name", sa.String(300)),
            sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("received_at", sa.DateTime()),
            sa.Column("received_by", sa.String(100)),
            sa.Column("exclude_reason", sa.String(500)),
            sa.Column("exchange_reason", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "batch_id", "student_id", "textbook_id", name="uk_aa_tb_dist_record"))

    if not _has(bind, "t_aa_textbook_fee_ledger"):
        op.create_table(
            "t_aa_textbook_fee_ledger", *_pk_tenant(),
            sa.Column("distribution_record_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("textbook_name", sa.String(300)),
            sa.Column("amount", sa.Numeric(8, 2), nullable=False, server_default="0"),
            sa.Column("paid_at", sa.DateTime()),
            sa.Column("waive_reason", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="UNPAID"),
            *_COMMON,
            sa.UniqueConstraint("tenant_id", "distribution_record_id", name="uk_aa_tb_fee"))


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_textbook_fee_ledger", "t_aa_textbook_distribution_record",
              "t_aa_textbook_distribution_batch", "t_aa_textbook_order_item",
              "t_aa_textbook_order_batch", "t_aa_textbook_review_batch_item",
              "t_aa_textbook_review_batch", "t_aa_textbook_selection", "t_aa_textbook"):
        if _has(bind, t):
            op.drop_table(t)
