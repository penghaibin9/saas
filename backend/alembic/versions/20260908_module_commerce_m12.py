"""M1/M2 module-commerce catalogue, order lines and entitlement sources.

Revision ID: 20260908_module_commerce_m12
Revises: 20260901_orientation_self_activate_o6
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260908_module_commerce_m12"
down_revision = "20260901_orientation_self_activate_o6"
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
        "t_commercial_sku_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sku_code", sa.String(64), nullable=False),
        sa.Column("sku_revision", sa.BigInteger(), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("module_key", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("lifecycle_policy_version", sa.String(64), nullable=False),
        sa.Column("publish_status", sa.String(20), nullable=False, server_default="PUBLISHED"),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.String(500), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_code", "sku_revision", name="uk_commercial_sku_version"),
        sa.UniqueConstraint("content_hash", name="uk_commercial_sku_content_hash"),
    )
    op.create_index("ix_t_commercial_sku_version_tenant_id", "t_commercial_sku_version", ["tenant_id"])

    op.create_table(
        "t_commercial_order_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.BigInteger(), nullable=False),
        sa.Column("sku_code", sa.String(64), nullable=True),
        sa.Column("sku_revision", sa.BigInteger(), nullable=True),
        sa.Column("sku_content_hash", sa.String(64), nullable=True),
        sa.Column("module_key", sa.String(64), nullable=True),
        sa.Column("module_generation", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("service_start_at", sa.DateTime(), nullable=True),
        sa.Column("service_end_at", sa.DateTime(), nullable=True),
        sa.Column("sku_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("feature_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("quota_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("fulfillment_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("fulfilled_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["order_id"], ["t_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "line_no", name="uk_commercial_order_item_line"),
    )
    op.create_index("ix_t_commercial_order_item_tenant_id", "t_commercial_order_item", ["tenant_id"])
    op.create_index("ix_t_commercial_order_item_order_id", "t_commercial_order_item", ["order_id"])
    op.create_index("ix_t_commercial_order_item_module_key", "t_commercial_order_item", ["module_key"])
    op.create_index("ix_commercial_order_item_tenant_module_window", "t_commercial_order_item", ["tenant_id", "module_key", "service_start_at", "service_end_at"])

    op.create_table(
        "t_tenant_commercial_profile",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("reader_version", sa.String(20), nullable=False, server_default="LEGACY"),
        sa.Column("migration_status", sa.String(32), nullable=False, server_default="NOT_STARTED"),
        sa.Column("shadow_digest", sa.String(64), nullable=True),
        sa.Column("switched_at", sa.DateTime(), nullable=True),
        sa.Column("switch_reason", sa.String(500), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uk_tenant_commercial_profile"),
    )
    op.create_index("ix_t_tenant_commercial_profile_tenant_id", "t_tenant_commercial_profile", ["tenant_id"])

    op.create_table(
        "t_tenant_module_state",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("module_key", sa.String(64), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("lifecycle_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("data_state", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("purged_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "module_key", name="uk_tenant_module_state"),
    )
    op.create_index("ix_t_tenant_module_state_tenant_id", "t_tenant_module_state", ["tenant_id"])
    op.create_index("ix_tenant_module_state_data", "t_tenant_module_state", ["tenant_id", "data_state"])

    op.create_table(
        "t_tenant_module_subscription_source",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("module_key", sa.String(64), nullable=False),
        sa.Column("module_generation", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(100), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=True),
        sa.Column("feature_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("quota_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column("approval_ref", sa.String(100), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        *_common_columns(),
        sa.ForeignKeyConstraint(["order_item_id"], ["t_commercial_order_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_type", "source_ref", "module_key", name="uk_tenant_module_source"),
    )
    op.create_index("ix_t_tenant_module_subscription_source_tenant_id", "t_tenant_module_subscription_source", ["tenant_id"])
    op.create_index("ix_t_tenant_module_subscription_source_order_item_id", "t_tenant_module_subscription_source", ["order_item_id"])
    op.create_index("ix_tenant_module_source_window", "t_tenant_module_subscription_source", ["tenant_id", "module_key", "status", "starts_at", "ends_at"])

    op.execute(sa.text("""
        INSERT INTO t_commercial_order_item
          (tenant_id, order_id, line_no, sku_code, sku_revision, sku_content_hash,
           module_key, module_generation, quantity, unit_price, discount_amount,
           net_amount, currency, service_start_at, service_end_at, sku_snapshot_json,
           feature_snapshot_json, quota_snapshot_json, fulfillment_status,
           created_at, created_by, updated_at, updated_by, is_deleted, version)
        SELECT o.tenant_id, o.id, 1, NULL, NULL, NULL, NULL, NULL, 1,
               o.amount, 0, o.amount, NULL, o.start_at, o.end_at, NULL,
               JSON_OBJECT(), JSON_OBJECT(), 'LEGACY_UNALLOCATED',
               COALESCE(o.created_at, NOW()), o.created_by,
               COALESCE(o.updated_at, COALESCE(o.created_at, NOW())), o.updated_by,
               FALSE, 0
          FROM t_order o
         WHERE o.is_deleted = FALSE
           AND NOT EXISTS (
               SELECT 1 FROM t_commercial_order_item i
                WHERE i.order_id = o.id AND i.is_deleted = FALSE
           )
    """))


def downgrade() -> None:
    op.drop_table("t_tenant_module_subscription_source")
    op.drop_table("t_tenant_module_state")
    op.drop_table("t_tenant_commercial_profile")
    op.drop_table("t_commercial_order_item")
    op.drop_table("t_commercial_sku_version")
