"""SYS-06：权限包、交付角色模板、自定义角色来源与通配退役队列。

本迁移只建治理层，**不改动鉴权路径**：真实鉴权仍走 app.core.permissions.ROLE_PERMISSIONS
常量。切换到数据库需要双读对账，属于后续独立步骤——在这里一次性切换会让全系统登录与
权限同时受影响，风险不可控。

Revision ID: 0158_permission_governance
Revises: 0157_config_governance
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0158_permission_governance"
down_revision = "0157_config_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0158_permission_governance requires MySQL")


def _common_columns() -> list:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_permission_bundle"):
        op.create_table(
            "t_permission_bundle",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("bundle_code", sa.String(128), nullable=False),
            sa.Column("bundle_name", sa.String(128), nullable=False),
            sa.Column("owner_domain", sa.String(64), nullable=False),
            sa.Column("risk_level", sa.String(16), nullable=False, server_default="NORMAL"),
            sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("description", sa.String(500)),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_permission_bundle_tenant_id", "t_permission_bundle", ["tenant_id"])
        op.create_unique_constraint(
            "uk_bundle_tenant_code", "t_permission_bundle", ["tenant_id", "bundle_code"]
        )
        op.create_index("idx_bundle_owner_status", "t_permission_bundle", ["owner_domain", "status"])

    if not insp.has_table("t_permission_bundle_item"):
        op.create_table(
            "t_permission_bundle_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("bundle_id", sa.BigInteger(), nullable=False),
            sa.Column("permission_code", sa.String(160), nullable=False),
            sa.Column("effect", sa.String(8), nullable=False, server_default="ALLOW"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_permission_bundle_item_tenant_id", "t_permission_bundle_item", ["tenant_id"])
        op.create_index("ix_t_permission_bundle_item_bundle_id", "t_permission_bundle_item", ["bundle_id"])
        op.create_unique_constraint(
            "uk_bundle_permission", "t_permission_bundle_item", ["bundle_id", "permission_code", "effect"]
        )
        op.create_index("idx_bundle_item_permission", "t_permission_bundle_item", ["permission_code"])

    if not insp.has_table("t_role_template"):
        op.create_table(
            "t_role_template",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("template_code", sa.String(64), nullable=False),
            sa.Column("template_name", sa.String(128), nullable=False),
            sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("bundle_codes_json", sa.JSON()),
            sa.Column("permission_ceiling_json", sa.JSON(), nullable=False),
            sa.Column("wildcard_json", sa.JSON()),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_role_template_tenant_id", "t_role_template", ["tenant_id"])
        op.create_unique_constraint(
            "uk_role_template_version", "t_role_template", ["tenant_id", "template_code", "template_version"]
        )
        op.create_index("idx_role_template_status", "t_role_template", ["tenant_id", "status"])

    if not insp.has_table("t_custom_role_source"):
        op.create_table(
            "t_custom_role_source",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("source_template_code", sa.String(64), nullable=False),
            sa.Column("source_template_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("permission_codes_json", sa.JSON(), nullable=False),
            sa.Column("drift_json", sa.JSON()),
            sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_custom_role_source_tenant_id", "t_custom_role_source", ["tenant_id"])
        op.create_unique_constraint(
            "uk_custom_role_source", "t_custom_role_source", ["tenant_id", "role_code"]
        )
        op.create_index(
            "idx_custom_role_template", "t_custom_role_source", ["tenant_id", "source_template_code"]
        )

    if not insp.has_table("t_wildcard_retirement"):
        op.create_table(
            "t_wildcard_retirement",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("wildcard_code", sa.String(160), nullable=False),
            sa.Column("expanded_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expanded_json", sa.JSON()),
            sa.Column("replacement_json", sa.JSON()),
            sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
            sa.Column("note", sa.String(1000)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_wildcard_retirement_tenant_id", "t_wildcard_retirement", ["tenant_id"])
        op.create_unique_constraint(
            "uk_wildcard_retirement", "t_wildcard_retirement", ["tenant_id", "role_code", "wildcard_code"]
        )
        op.create_index("idx_wildcard_status", "t_wildcard_retirement", ["tenant_id", "status"])


def downgrade() -> None:
    for table in (
        "t_wildcard_retirement",
        "t_custom_role_source",
        "t_role_template",
        "t_permission_bundle_item",
        "t_permission_bundle",
    ):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
