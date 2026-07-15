"""教学资源续卡 R3：实训室资源(t_aa_lab_resource)/设备资源(t_aa_equipment)/
实训室预约(t_aa_lab_booking)/资源维修工单(t_aa_resource_repair) 四张新表。

复用教室字典(t_aa_classroom)+教室预约(t_aa_classroom_booking)已验证的字段/状态机口径，
不改动这两张已上线表的结构。资源占用/资源冲突/资源统计三个三级模块为纯只读聚合查询，
不需要新表。

Revision ID: aa_resources_r3
Revises: aa_course_lib_tier1_r2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_resources_r3"
down_revision = "aa_quality_r3"
branch_labels = None
depends_on = None


def _has(bind, table) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has(bind, "t_aa_lab_resource"):
        op.create_table(
            "t_aa_lab_resource",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("lab_code", sa.String(length=50), nullable=False),
            sa.Column("lab_name", sa.String(length=100), nullable=False),
            sa.Column("building_name", sa.String(length=100)),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lab_type", sa.String(length=30), nullable=False, server_default="SKILL"),
            sa.Column("responsible_name", sa.String(length=50)),
            sa.Column("responsible_key", sa.String(length=100)),
            sa.Column("remark", sa.String(length=500)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="AVAILABLE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "lab_code", name="uk_aa_lab_resource"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_aa_lab_resource_tenant", "t_aa_lab_resource", ["tenant_id"])
        op.create_index("ix_aa_lab_resource_code", "t_aa_lab_resource", ["lab_code"])
        op.create_index("ix_aa_lab_resource_status", "t_aa_lab_resource", ["status"])

    if not _has(bind, "t_aa_equipment"):
        op.create_table(
            "t_aa_equipment",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("equipment_code", sa.String(length=50), nullable=False),
            sa.Column("equipment_name", sa.String(length=100), nullable=False),
            sa.Column("spec_model", sa.String(length=200)),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("owner_kind", sa.String(length=20), nullable=False, server_default="NONE"),
            sa.Column("owner_id", sa.BigInteger()),
            sa.Column("owner_label", sa.String(length=150)),
            sa.Column("responsible_name", sa.String(length=50)),
            sa.Column("purchase_date", sa.String(length=20)),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="IN_USE"),
            sa.Column("remark", sa.String(length=500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "equipment_code", name="uk_aa_equipment"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_aa_equipment_tenant", "t_aa_equipment", ["tenant_id"])
        op.create_index("ix_aa_equipment_code", "t_aa_equipment", ["equipment_code"])
        op.create_index("ix_aa_equipment_status", "t_aa_equipment", ["status"])
        op.create_index("ix_aa_equipment_owner", "t_aa_equipment", ["owner_kind", "owner_id"])

    if not _has(bind, "t_aa_lab_booking"):
        op.create_table(
            "t_aa_lab_booking",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("lab_id", sa.BigInteger(), nullable=False),
            sa.Column("lab_text", sa.String(length=100)),
            sa.Column("booking_date", sa.String(length=20), nullable=False),
            sa.Column("slot_no", sa.Integer(), nullable=False),
            sa.Column("purpose", sa.String(length=300)),
            sa.Column("applicant_key", sa.String(length=100)),
            sa.Column("applicant_name", sa.String(length=100)),
            sa.Column("review_reason", sa.String(length=300)),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_aa_lab_booking", "t_aa_lab_booking", ["tenant_id", "lab_id", "booking_date"])

    if not _has(bind, "t_aa_resource_repair"):
        op.create_table(
            "t_aa_resource_repair",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("resource_kind", sa.String(length=20), nullable=False),
            sa.Column("resource_id", sa.BigInteger(), nullable=False),
            sa.Column("resource_label", sa.String(length=150)),
            sa.Column("fault_desc", sa.String(length=500), nullable=False),
            sa.Column("reporter_key", sa.String(length=100)),
            sa.Column("reporter_name", sa.String(length=100)),
            sa.Column("repair_note", sa.String(length=500)),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="REPORTED"),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB", mysql_charset="utf8mb4",
        )
        op.create_index("ix_aa_resource_repair_tenant", "t_aa_resource_repair", ["tenant_id"])
        op.create_index("ix_aa_resource_repair_res", "t_aa_resource_repair", ["resource_kind", "resource_id"])
        op.create_index("ix_aa_resource_repair_status", "t_aa_resource_repair", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    for t in ("t_aa_resource_repair", "t_aa_lab_booking", "t_aa_equipment", "t_aa_lab_resource"):
        if _has(bind, t):
            op.drop_table(t)
