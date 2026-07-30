"""公共文件冻结中心阶段 6：毕业设计材料规则与公共版本中心

Revision ID: 0150_graduation_material_center
Revises: 0149_affairs_material_center
Create Date: 2026-07-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0150_graduation_material_center"
down_revision = "0149_affairs_material_center"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "t_gd_material_rule" not in tables:
        op.create_table(
            "t_gd_material_rule",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("batch_id", sa.BigInteger()),
            sa.Column("rule_code", sa.String(80), nullable=False),
            sa.Column("rule_name", sa.String(200), nullable=False),
            sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("applicable_scope_json", sa.JSON()),
            sa.Column("required_items_json", sa.JSON()),
            sa.Column("allowed_ext_json", sa.JSON()),
            sa.Column("max_files", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("max_size_bytes", sa.BigInteger(), nullable=False, server_default=str(50 * 1024 * 1024)),
            sa.Column("remark", sa.String(500)),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint(
                "tenant_id", "batch_id", "rule_code", "rule_version",
                name="uk_gd_material_rule_version",
            ),
        )
        op.create_index("ix_t_gd_material_rule_tenant_id", "t_gd_material_rule", ["tenant_id"])
        op.create_index("ix_t_gd_material_rule_batch_id", "t_gd_material_rule", ["batch_id"])
        op.create_index(
            "ix_gd_material_rule_active", "t_gd_material_rule",
            ["tenant_id", "batch_id", "status", "is_deleted"],
        )

    tables = _tables()
    if "t_gd_material_item" not in tables:
        op.create_table(
            "t_gd_material_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("rule_id", sa.BigInteger(), nullable=False),
            sa.Column("biz_stage", sa.String(30), nullable=False),
            sa.Column("material_code", sa.String(100), nullable=False),
            sa.Column("material_name", sa.String(200), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("allowed_ext_json", sa.JSON()),
            sa.Column("max_files", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_size_bytes", sa.BigInteger(), nullable=False, server_default=str(50 * 1024 * 1024)),
            sa.Column("description", sa.String(500)),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.UniqueConstraint(
                "tenant_id", "rule_id", "material_code",
                name="uk_gd_material_item_code",
            ),
        )
        op.create_index("ix_t_gd_material_item_tenant_id", "t_gd_material_item", ["tenant_id"])
        op.create_index("ix_t_gd_material_item_rule_id", "t_gd_material_item", ["rule_id"])
        op.create_index(
            "ix_gd_material_item_stage", "t_gd_material_item",
            ["tenant_id", "rule_id", "biz_stage", "sort_no", "is_deleted"],
        )


def downgrade() -> None:
    tables = _tables()
    if "t_gd_material_item" in tables:
        op.drop_table("t_gd_material_item")
    tables = _tables()
    if "t_gd_material_rule" in tables:
        op.drop_table("t_gd_material_rule")
