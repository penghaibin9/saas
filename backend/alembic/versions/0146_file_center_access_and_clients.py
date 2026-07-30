"""公共文件中心阶段 2：对象绑定与统一授权

Revision ID: 0146_file_access_clients
Revises: 0145_file_security_foundation
Create Date: 2026-07-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0146_file_access_clients"
down_revision = "0145_file_security_foundation"
branch_labels = None
depends_on = None

TABLE = "t_file_binding"


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if TABLE in _tables():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("biz_type", sa.String(50), nullable=False),
        sa.Column("biz_id", sa.String(64), nullable=False),
        sa.Column("relation_type", sa.String(40), nullable=False, server_default="ATTACHMENT"),
        sa.Column("subject_type", sa.String(30), nullable=False, server_default="BUSINESS_OBJECT"),
        sa.Column("subject_id", sa.String(64)),
        sa.Column("batch_id", sa.String(64)),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("scope_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id", "file_id", "biz_type", "biz_id", "relation_type",
            name="uk_file_binding_relation",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_t_file_binding_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_t_file_binding_file_id", TABLE, ["file_id"])
    op.create_index("ix_file_binding_business", TABLE, ["tenant_id", "biz_type", "biz_id", "is_current"])
    op.create_index("ix_file_binding_subject", TABLE, ["tenant_id", "subject_type", "subject_id"])
    op.create_index("ix_file_binding_batch", TABLE, ["tenant_id", "batch_id"])


def downgrade() -> None:
    if TABLE in _tables():
        op.drop_table(TABLE)
