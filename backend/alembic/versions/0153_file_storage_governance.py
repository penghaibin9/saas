"""阶段 9：租户配额、保留策略、法律保留与过期清理。

Revision ID: 0153_file_storage_governance
Revises: 0152_file_center_cos_production
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0153_file_storage_governance"
down_revision = "0152_file_center_cos_production"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0153_file_storage_governance requires MySQL")


def _columns(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    _require_mysql()
    columns = _columns("t_file_object")
    for name, column in (
        ("retention_until", sa.Column("retention_until", sa.DateTime())),
        ("legal_hold", sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("deleted_at", sa.Column("deleted_at", sa.DateTime())),
    ):
        if name not in columns:
            op.add_column("t_file_object", column)
    if "ix_file_retention_cleanup" not in _indexes("t_file_object"):
        op.create_index(
            "ix_file_retention_cleanup",
            "t_file_object",
            ["tenant_id", "legal_hold", "is_deleted", "retention_until", "id"],
        )

    if not inspect(op.get_bind()).has_table("t_file_retention_policy"):
        op.create_table(
            "t_file_retention_policy",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("policy_code", sa.String(100), nullable=False),
            sa.Column("module_code", sa.String(64)),
            sa.Column("biz_type", sa.String(80)),
            sa.Column("storage_zone", sa.String(30)),
            sa.Column("retention_days", sa.Integer(), nullable=False),
            sa.Column("cleanup_action", sa.String(30), nullable=False, server_default="DELETE_BYTES"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("description", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "policy_code", name="uk_file_retention_policy_code"),
        )
        op.create_index("ix_file_retention_policy_match", "t_file_retention_policy", ["tenant_id", "is_active", "module_code", "biz_type", "storage_zone", "priority"])

    if not inspect(op.get_bind()).has_table("t_tenant_storage_quota"):
        op.create_table(
            "t_tenant_storage_quota",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("total_quota_bytes", sa.BigInteger(), nullable=False),
            sa.Column("warning_percent", sa.Integer(), nullable=False, server_default="80"),
            sa.Column("hard_limit_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("module_quota_json", sa.JSON()),
            sa.Column("description", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", name="uk_tenant_storage_quota"),
        )
        op.create_index("ix_tenant_storage_quota_enabled", "t_tenant_storage_quota", ["tenant_id", "hard_limit_enabled", "is_deleted"])


def downgrade() -> None:
    _require_mysql()
    inspector = inspect(op.get_bind())
    if inspector.has_table("t_tenant_storage_quota"):
        op.drop_table("t_tenant_storage_quota")
    if inspector.has_table("t_file_retention_policy"):
        op.drop_table("t_file_retention_policy")
    if "ix_file_retention_cleanup" in _indexes("t_file_object"):
        op.drop_index("ix_file_retention_cleanup", table_name="t_file_object")
    columns = _columns("t_file_object")
    for name in ("deleted_at", "legal_hold", "retention_until"):
        if name in columns:
            op.drop_column("t_file_object", name)
