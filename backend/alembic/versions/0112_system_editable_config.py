"""系统管理中心可编辑配置三表：t_sys_config / t_data_scope_rule / t_menu_node。

Revision ID: 0112_system_editable_config
Revises: 0111_immutable_acceptance_summary

经产品负责人明确决策扩展冻结册：系统配置/数据范围规则/菜单从"推导/硬编码"改为真实可编辑落库。
上层强制/读取路径在缺表或空数据时回落基线行为，平滑上线。

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时这三张表可能已
提前创建，故先查表再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0112_system_editable_config"
down_revision = "0111_immutable_acceptance_summary"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _common_columns() -> list:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    if not _has_table("t_sys_config"):
        op.create_table(
            "t_sys_config",
            *_common_columns(),
            sa.Column("config_key", sa.String(length=100), nullable=False),
            sa.Column("config_group", sa.String(length=50), nullable=True),
            sa.Column("config_name", sa.String(length=100), nullable=True),
            sa.Column("value_text", sa.String(length=500), nullable=True),
            sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("remark", sa.String(length=500), nullable=True),
            sa.UniqueConstraint("tenant_id", "config_key", name="uk_sysconfig_tenant_key"),
        )
        op.create_index("ix_sysconfig_tenant", "t_sys_config", ["tenant_id"])

    if not _has_table("t_data_scope_rule"):
        op.create_table(
            "t_data_scope_rule",
            *_common_columns(),
            sa.Column("rule_name", sa.String(length=100), nullable=False),
            sa.Column("role_code", sa.String(length=50), nullable=True),
            sa.Column("scope_type", sa.String(length=50), nullable=False),
            sa.Column("target_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
            sa.Column("remark", sa.String(length=500), nullable=True),
        )
        op.create_index("ix_scoperule_tenant", "t_data_scope_rule", ["tenant_id"])
        op.create_index("ix_scoperule_role", "t_data_scope_rule", ["role_code"])

    if not _has_table("t_menu_node"):
        op.create_table(
            "t_menu_node",
            *_common_columns(),
            sa.Column("menu_code", sa.String(length=100), nullable=False),
            sa.Column("parent_code", sa.String(length=100), nullable=True),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("path", sa.String(length=200), nullable=True),
            sa.Column("icon", sa.String(length=50), nullable=True),
            sa.Column("module_code", sa.String(length=50), nullable=True),
            sa.Column("permission_key", sa.String(length=100), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.UniqueConstraint("tenant_id", "menu_code", name="uk_menu_tenant_code"),
        )
        op.create_index("ix_menu_tenant", "t_menu_node", ["tenant_id"])
        op.create_index("ix_menu_parent", "t_menu_node", ["parent_code"])


def downgrade() -> None:
    for table_name in ("t_menu_node", "t_data_scope_rule", "t_sys_config"):
        if _has_table(table_name):
            op.drop_table(table_name)
