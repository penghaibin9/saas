"""SYS-11：配置定义、分层覆盖与激活流水。

不搬迁 t_sys_config：学校已有的安全配置（登录锁定阈值等）仍在原表，强制层读取路径不变。
本迁移只补"定义 + 分层覆盖 + 未来生效 + 变更流水"，解析时按继承链合并，避免升级瞬间
改变任何已生效的安全行为。

Revision ID: 0157_config_governance
Revises: 0156_organization_version_and_assignment
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0157_config_governance"
down_revision = "0156_organization_version_and_assignment"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0157_config_governance requires MySQL")


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

    if not insp.has_table("t_config_definition"):
        op.create_table(
            "t_config_definition",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("config_key", sa.String(160), nullable=False),
            sa.Column("domain_code", sa.String(64), nullable=False),
            sa.Column("config_name", sa.String(200)),
            sa.Column("value_type", sa.String(24), nullable=False, server_default="STRING"),
            sa.Column("validation_json", sa.JSON()),
            sa.Column("default_json", sa.JSON()),
            sa.Column("platform_floor_json", sa.JSON()),
            sa.Column("school_editable", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("owner_code", sa.String(64), nullable=False, server_default="SYSTEM"),
            sa.Column("consumer_json", sa.JSON()),
            sa.Column("cache_scope", sa.String(32), nullable=False, server_default="TENANT"),
            sa.Column("risk_level", sa.String(16), nullable=False, server_default="NORMAL"),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_unique_constraint("uk_config_definition_key", "t_config_definition", ["config_key"])
        op.create_index(
            "idx_config_definition_domain_status", "t_config_definition", ["domain_code", "status"]
        )

    if not insp.has_table("t_config_override"):
        op.create_table(
            "t_config_override",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("config_key", sa.String(160), nullable=False),
            sa.Column("scope_type", sa.String(24), nullable=False, server_default="TENANT"),
            sa.Column("scope_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("value_json", sa.JSON(), nullable=False),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            sa.Column("reason", sa.String(1000)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_config_override_tenant_id", "t_config_override", ["tenant_id"])
        op.create_index("ix_t_config_override_config_key", "t_config_override", ["config_key"])
        op.create_index("ix_t_config_override_status", "t_config_override", ["status"])
        op.create_unique_constraint(
            "uk_config_override_scope",
            "t_config_override",
            ["tenant_id", "config_key", "scope_type", "scope_id", "effective_at"],
        )
        op.create_index(
            "idx_config_override_effective",
            "t_config_override",
            ["tenant_id", "config_key", "status", "effective_at", "expires_at"],
        )

    if not insp.has_table("t_config_activation"):
        op.create_table(
            "t_config_activation",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("config_key", sa.String(160), nullable=False),
            sa.Column("scope_type", sa.String(24), nullable=False),
            sa.Column("scope_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("before_json", sa.JSON()),
            sa.Column("after_json", sa.JSON()),
            sa.Column("actor_user_id", sa.BigInteger()),
            sa.Column("reason", sa.String(1000)),
            sa.Column("trace_id", sa.String(64)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_config_activation_tenant_id", "t_config_activation", ["tenant_id"])
        op.create_index("ix_t_config_activation_config_key", "t_config_activation", ["config_key"])
        op.create_index("ix_t_config_activation_trace_id", "t_config_activation", ["trace_id"])
        op.create_index(
            "idx_config_activation_key_time", "t_config_activation", ["tenant_id", "config_key", "created_at"]
        )


def downgrade() -> None:
    for table in ("t_config_activation", "t_config_override", "t_config_definition"):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
