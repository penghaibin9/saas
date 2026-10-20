"""M8 after-sales linkage and actual service-cost facts.

Revision ID: 20260909_module_commerce_m8_operations
Revises: 20260909_module_commerce_m8_finance

No entitlement, payment, refund-provider or ticket-state data is duplicated here.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260909_module_commerce_m8_operations"
down_revision = "20260909_module_commerce_m8_finance"
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
        "t_commercial_after_sales_link",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("refund_case_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("support_ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("link_type", sa.String(40), nullable=False, server_default="REFUND_ENTITLEMENT_REVIEW"),
        sa.Column("module_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("settlement_ref_snapshot", sa.String(160), nullable=True),
        sa.Column("linked_at", sa.DateTime(), nullable=False),
        sa.Column("linked_by", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["refund_case_id"], ["t_commercial_refund_case.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["t_order.id"]),
        sa.ForeignKeyConstraint(["support_ticket_id"], ["t_support_ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "refund_case_id", name="uk_commercial_after_sales_refund"),
        sa.UniqueConstraint("tenant_id", "support_ticket_id", name="uk_commercial_after_sales_ticket"),
    )
    op.create_index("ix_t_commercial_after_sales_link_tenant_id", "t_commercial_after_sales_link", ["tenant_id"])
    op.create_index("ix_t_commercial_after_sales_link_refund_case_id", "t_commercial_after_sales_link", ["refund_case_id"])
    op.create_index("ix_t_commercial_after_sales_link_order_id", "t_commercial_after_sales_link", ["order_id"])
    op.create_index("ix_t_commercial_after_sales_link_support_ticket_id", "t_commercial_after_sales_link", ["support_ticket_id"])
    op.create_index("ix_commercial_after_sales_order", "t_commercial_after_sales_link", ["tenant_id", "order_id", "id"])

    op.create_table(
        "t_commercial_service_cost_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("request_key_hash", sa.String(64), nullable=False),
        sa.Column("request_payload_hash", sa.String(64), nullable=False),
        sa.Column("cost_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("support_ticket_id", sa.BigInteger(), nullable=True),
        sa.Column("refund_case_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("external_ref", sa.String(160), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("recorded_by", sa.BigInteger(), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["support_ticket_id"], ["t_support_ticket.id"]),
        sa.ForeignKeyConstraint(["refund_case_id"], ["t_commercial_refund_case.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["t_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "request_key_hash", name="uk_commercial_service_cost_request"),
    )
    op.create_index("ix_t_commercial_service_cost_record_tenant_id", "t_commercial_service_cost_record", ["tenant_id"])
    op.create_index("ix_t_commercial_service_cost_record_support_ticket_id", "t_commercial_service_cost_record", ["support_ticket_id"])
    op.create_index("ix_t_commercial_service_cost_record_refund_case_id", "t_commercial_service_cost_record", ["refund_case_id"])
    op.create_index("ix_t_commercial_service_cost_record_order_id", "t_commercial_service_cost_record", ["order_id"])
    op.create_index("ix_commercial_service_cost_time", "t_commercial_service_cost_record", ["tenant_id", "occurred_at", "id"])
    op.create_index("ix_commercial_service_cost_ticket", "t_commercial_service_cost_record", ["tenant_id", "support_ticket_id", "id"])
    op.create_index("ix_commercial_service_cost_order", "t_commercial_service_cost_record", ["tenant_id", "order_id", "id"])


def downgrade() -> None:
    op.drop_table("t_commercial_service_cost_record")
    op.drop_table("t_commercial_after_sales_link")
