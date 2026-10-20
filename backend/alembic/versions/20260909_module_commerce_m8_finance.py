"""M8 manual refund and invoice finance-control facts.

Revision ID: 20260909_module_commerce_m8_finance
Revises: 20260908_merge_commerce_sa

These tables record reviewed control-plane facts only. They do not execute refunds,
open invoices, change PlatformOrder payment truth or alter module entitlements.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260909_module_commerce_m8_finance"
down_revision = "20260908_merge_commerce_sa"
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    op.create_table(
        "t_commercial_refund_case",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("case_no", sa.String(64), nullable=False),
        sa.Column("request_key_hash", sa.String(64), nullable=False),
        sa.Column("request_payload_hash", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("order_paid_amount_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="REQUESTED"),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approval_note", sa.String(500), nullable=True),
        sa.Column("rejected_by", sa.BigInteger(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("settled_by", sa.BigInteger(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("settlement_ref", sa.String(160), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["order_id"], ["t_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uk_commercial_refund_case_no"),
        sa.UniqueConstraint("request_key_hash", name="uk_commercial_refund_request_key"),
    )
    op.create_index("ix_t_commercial_refund_case_tenant_id", "t_commercial_refund_case", ["tenant_id"])
    op.create_index("ix_t_commercial_refund_case_order_id", "t_commercial_refund_case", ["order_id"])
    op.create_index("ix_t_commercial_refund_case_status", "t_commercial_refund_case", ["status"])
    op.create_index("ix_commercial_refund_tenant_order_status", "t_commercial_refund_case", ["tenant_id", "order_id", "status", "id"])

    op.create_table(
        "t_commercial_invoice_case",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("request_no", sa.String(64), nullable=False),
        sa.Column("request_key_hash", sa.String(64), nullable=False),
        sa.Column("request_payload_hash", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("invoice_title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="REQUESTED"),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("issued_by", sa.BigInteger(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("external_invoice_ref", sa.String(160), nullable=True),
        sa.Column("invoice_file_id", sa.BigInteger(), nullable=True),
        sa.Column("voided_by", sa.BigInteger(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("void_reason", sa.String(500), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["order_id"], ["t_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_no", name="uk_commercial_invoice_request_no"),
        sa.UniqueConstraint("request_key_hash", name="uk_commercial_invoice_request_key"),
    )
    op.create_index("ix_t_commercial_invoice_case_tenant_id", "t_commercial_invoice_case", ["tenant_id"])
    op.create_index("ix_t_commercial_invoice_case_order_id", "t_commercial_invoice_case", ["order_id"])
    op.create_index("ix_t_commercial_invoice_case_status", "t_commercial_invoice_case", ["status"])
    op.create_index("ix_t_commercial_invoice_case_invoice_file_id", "t_commercial_invoice_case", ["invoice_file_id"])
    op.create_index("ix_commercial_invoice_tenant_order_status", "t_commercial_invoice_case", ["tenant_id", "order_id", "status", "id"])


def downgrade() -> None:
    op.drop_table("t_commercial_invoice_case")
    op.drop_table("t_commercial_refund_case")
