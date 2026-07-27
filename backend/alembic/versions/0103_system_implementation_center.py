"""Implementation and preset center; merge current migration heads.

Revision ID: 0103_system_implementation
Revises: 0102_student_directory, 0099_student_realname_index

兼容说明：0001 历史迁移会导入运行时的当前 metadata，因此新建空库时可能已提前
创建本 revision 的表。这里逐表检查后再创建，避免 MySQL 从零升级重复建表；
既有数据库中尚未创建的表仍按本 revision 的原始 DDL 创建。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0103_system_implementation"
down_revision = ("0102_student_directory", "0099_student_realname_index")
branch_labels = None
depends_on = None


def _common():
    return [sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("t_system_implementation_project"):
        op.create_table("t_system_implementation_project", *_common(),
            sa.Column("project_no", sa.String(50), nullable=False), sa.Column("project_name", sa.String(100), nullable=False),
            sa.Column("profile_code", sa.String(50), nullable=False), sa.Column("status", sa.String(40), nullable=False),
            sa.Column("owner_id", sa.BigInteger()), sa.Column("target_date", sa.Date()),
            sa.Column("preview_json", sa.JSON()), sa.Column("preview_hash", sa.String(64)),
            sa.Column("applied_at", sa.DateTime()), sa.Column("accepted_at", sa.DateTime()),
            sa.Column("accepted_by", sa.BigInteger()), sa.Column("acceptance_comment", sa.String(500)),
            sa.UniqueConstraint("tenant_id", "project_no", name="uk_sys_impl_project_no"))
        op.create_index("ix_sys_impl_project_tenant_status", "t_system_implementation_project", ["tenant_id", "status"])

    if not _has_table("t_system_implementation_section"):
        op.create_table("t_system_implementation_section", *_common(),
            sa.Column("project_id", sa.BigInteger(), nullable=False), sa.Column("section_code", sa.String(50), nullable=False),
            sa.Column("schema_version", sa.String(20), nullable=False), sa.Column("source", sa.String(20), nullable=False),
            sa.Column("config_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
            sa.UniqueConstraint("tenant_id", "project_id", "section_code", name="uk_sys_impl_section"))
        op.create_index("ix_sys_impl_section_project", "t_system_implementation_section", ["tenant_id", "project_id"])

    if not _has_table("t_system_preset_installation"):
        op.create_table("t_system_preset_installation", *_common(),
            sa.Column("installation_no", sa.String(50), nullable=False), sa.Column("project_id", sa.BigInteger(), nullable=False),
            sa.Column("parent_id", sa.BigInteger()), sa.Column("change_type", sa.String(30), nullable=False),
            sa.Column("source_profile", sa.String(50), nullable=False), sa.Column("source_version", sa.String(30), nullable=False),
            sa.Column("snapshot_json", sa.JSON(), nullable=False), sa.Column("snapshot_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(30), nullable=False), sa.Column("reason", sa.String(500)),
            sa.Column("applied_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "installation_no", name="uk_sys_preset_install_no"))
        op.create_index("ix_sys_preset_install_tenant_status", "t_system_preset_installation", ["tenant_id", "status"])

    if not _has_table("t_system_implementation_check"):
        op.create_table("t_system_implementation_check", *_common(),
            sa.Column("project_id", sa.BigInteger(), nullable=False), sa.Column("check_code", sa.String(80), nullable=False),
            sa.Column("category_code", sa.String(50), nullable=False), sa.Column("check_name", sa.String(120), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False), sa.Column("result", sa.String(20), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=False), sa.Column("owner_role", sa.String(50)),
            sa.Column("confirmed_by", sa.BigInteger()), sa.Column("confirmed_at", sa.DateTime()), sa.Column("comment", sa.Text()),
            sa.UniqueConstraint("tenant_id", "project_id", "check_code", name="uk_sys_impl_check"))
        op.create_index("ix_sys_impl_check_project", "t_system_implementation_check", ["tenant_id", "project_id"])


def downgrade() -> None:
    for table_name in (
        "t_system_implementation_check",
        "t_system_preset_installation",
        "t_system_implementation_section",
        "t_system_implementation_project",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
