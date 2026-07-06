"""13A-P1: add t_affairs_class_cadre + t_affairs_audit_trail（学工中心首个 revision）

Revision ID: 0003_13a_p1_class_cadre
Revises: 0002_tenant_portal_config
Create Date: 2026-07-06

说明：显式 DDL 建两张 P1 新表，字段/索引与 app.models.affairs 完全一致，支持 downgrade。
存量库：不存在 → 创建；全新库 create_all 已建 → inspect 检测到已存在则幂等跳过。
两种场景都安全、不触碰其它表、不清数据。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003_13a_p1_class_cadre"
down_revision = "0002_tenant_portal_config"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")

CADRE = "t_affairs_class_cadre"
TRAIL = "t_affairs_audit_trail"


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _has(bind, CADRE):
        op.create_table(
            CADRE,
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("class_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("position", sa.String(length=50), nullable=False),
            sa.Column("term_code", sa.String(length=50), nullable=True),
            sa.Column("appointed_at", sa.DateTime(), nullable=True),
            sa.Column("removed_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("record_status", sa.String(length=50), nullable=False),
            sa.Column("void_reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
        )
        op.create_index("ix_t_affairs_class_cadre_tenant_id", CADRE, ["tenant_id"])
        op.create_index("ix_t_affairs_class_cadre_class_id", CADRE, ["class_id"])
        op.create_index("ix_t_affairs_class_cadre_student_id", CADRE, ["student_id"])

    if not _has(bind, TRAIL):
        op.create_table(
            TRAIL,
            sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
            sa.Column("biz_type", sa.String(length=50), nullable=False),
            sa.Column("biz_id", sa.BigInteger(), nullable=True),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("operator", sa.String(length=100), nullable=True),
            sa.Column("role_name", sa.String(length=100), nullable=True),
            sa.Column("detail", sa.String(length=1000), nullable=True),
            sa.Column("before_val", sa.String(length=1000), nullable=True),
            sa.Column("after_val", sa.String(length=1000), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
        )
        op.create_index("ix_t_affairs_audit_trail_tenant_id", TRAIL, ["tenant_id"])
        op.create_index("ix_t_affairs_audit_trail_biz_type", TRAIL, ["biz_type"])
        op.create_index("ix_t_affairs_audit_trail_biz_id", TRAIL, ["biz_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in (TRAIL, CADRE):
        if _has(bind, table):
            for idx in inspect(bind).get_indexes(table):
                op.drop_index(idx["name"], table_name=table)
            op.drop_table(table)
