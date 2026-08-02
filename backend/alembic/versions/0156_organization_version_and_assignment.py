"""SYS-04：组织变更版本与教职工任职。

组织仍是 t_college / t_major / t_class 三张实体表，本迁移不动它们的结构，只新增
"计划变更集"和"真实任职"两层。回填把既有的 counselor_id / head_teacher_id /
secretary_id 投影成 PROJECTED 任职，保留双读对账窗口后再退役旧字段。

Revision ID: 0156_organization_version_and_assignment
Revises: 0155_academic_calendar_governance
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0156_organization_version_and_assignment"
down_revision = "0155_academic_calendar_governance"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0156_organization_version_and_assignment requires MySQL")


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

    if not insp.has_table("t_org_version"):
        op.create_table(
            "t_org_version",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("version_code", sa.String(64), nullable=False),
            sa.Column("version_name", sa.String(200)),
            sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
            sa.Column("effective_at", sa.DateTime()),
            sa.Column("activated_at", sa.DateTime()),
            sa.Column("rolled_back_at", sa.DateTime()),
            sa.Column("reason", sa.String(1000)),
            sa.Column("impact_json", sa.JSON()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_org_version_tenant_id", "t_org_version", ["tenant_id"])
        op.create_index("ix_t_org_version_status", "t_org_version", ["status"])
        op.create_unique_constraint("uk_org_version_code", "t_org_version", ["tenant_id", "version_code"])
        op.create_index(
            "idx_org_version_status_effective", "t_org_version", ["tenant_id", "status", "effective_at"]
        )

    if not insp.has_table("t_org_version_item"):
        op.create_table(
            "t_org_version_item",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("version_id", sa.BigInteger(), nullable=False),
            sa.Column("change_type", sa.String(24), nullable=False),
            sa.Column("org_type", sa.String(24), nullable=False),
            sa.Column("org_node_id", sa.BigInteger()),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("before_json", sa.JSON()),
            sa.Column("applied_at", sa.DateTime()),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_org_version_item_tenant_id", "t_org_version_item", ["tenant_id"])
        op.create_index("ix_t_org_version_item_version_id", "t_org_version_item", ["version_id"])
        op.create_index("idx_org_version_item_version", "t_org_version_item", ["tenant_id", "version_id"])
        op.create_index(
            "idx_org_version_item_node", "t_org_version_item", ["tenant_id", "org_type", "org_node_id"]
        )

    if not insp.has_table("t_staff_assignment"):
        op.create_table(
            "t_staff_assignment",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("org_type", sa.String(24), nullable=False),
            sa.Column("org_node_id", sa.BigInteger(), nullable=False),
            sa.Column("assignment_type", sa.String(32), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source_type", sa.String(24), nullable=False, server_default="MANUAL"),
            sa.Column("source_id", sa.String(128)),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime()),
            sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
            sa.Column("reason", sa.String(1000)),
            *_common_columns(),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_staff_assignment_tenant_id", "t_staff_assignment", ["tenant_id"])
        op.create_index("ix_t_staff_assignment_user_id", "t_staff_assignment", ["user_id"])
        op.create_index("ix_t_staff_assignment_org_node_id", "t_staff_assignment", ["org_node_id"])
        op.create_index("ix_t_staff_assignment_status", "t_staff_assignment", ["status"])
        op.create_unique_constraint(
            "uk_staff_assignment",
            "t_staff_assignment",
            ["tenant_id", "user_id", "org_type", "org_node_id", "assignment_type", "effective_at"],
        )
        op.create_index(
            "idx_assignment_user_effective", "t_staff_assignment", ["tenant_id", "user_id", "status", "effective_at"]
        )
        op.create_index(
            "idx_assignment_org_effective",
            "t_staff_assignment",
            ["tenant_id", "org_type", "org_node_id", "status", "effective_at"],
        )

        # 回填既有投影任职。用固定 effective_at 常量而不是 NOW()，保证重复执行时
        # 唯一键能挡住重复插入（NOW() 每次不同会一直插新行）。
        backfill = """
            INSERT INTO t_staff_assignment
                (tenant_id, user_id, org_type, org_node_id, assignment_type, is_primary,
                 source_type, source_id, effective_at, status, reason,
                 created_at, updated_at, is_deleted, version)
            SELECT c.tenant_id, c.{col}, '{org_type}', c.id, '{assign_type}', 0,
                   'PROJECTED', CONCAT('{org_type}:', c.id), '1970-01-01 00:00:00', 'ACTIVE',
                   '0156 回填：来自既有 {col} 字段',
                   UTC_TIMESTAMP(), UTC_TIMESTAMP(), 0, 0
            FROM {table} c
            WHERE c.{col} IS NOT NULL AND c.is_deleted = 0
        """
        op.execute(backfill.format(table="t_class", col="counselor_id", org_type="CLASS", assign_type="COUNSELOR"))
        op.execute(
            backfill.format(table="t_class", col="head_teacher_id", org_type="CLASS", assign_type="HEAD_TEACHER")
        )
        op.execute(
            backfill.format(table="t_college", col="secretary_id", org_type="COLLEGE", assign_type="SECRETARY")
        )


def downgrade() -> None:
    for table in ("t_staff_assignment", "t_org_version_item", "t_org_version"):
        if inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
