"""Allow one WeChat identity to bind one account per tenant.

Revision ID: 0101_wx_multi_tenant
Revises: 0100_tenant_hotpaths
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0101_wx_multi_tenant"
down_revision = "0100_tenant_hotpaths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "t_wx_account_binding" not in inspect(bind).get_table_names():
        op.create_table(
            "t_wx_account_binding",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("wx_openid", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_by", sa.BigInteger(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "wx_openid", name="uk_wx_openid_tenant"),
        )
        op.create_index("ix_wx_binding_tenant_id", "t_wx_account_binding", ["tenant_id"])
        op.create_index("ix_wx_binding_wx_openid", "t_wx_account_binding", ["wx_openid"])
        op.create_index("ix_wx_binding_user_id", "t_wx_account_binding", ["user_id"])
        op.create_index("ix_wx_binding_tenant_user_active", "t_wx_account_binding",
                        ["tenant_id", "user_id", "is_deleted", "status"])

    # Existing one-to-one bindings become the first school binding. INSERT IGNORE
    # makes reruns safe on MySQL after an interrupted deployment.
    if bind.dialect.name == "mysql":
        op.execute(sa.text("""
            INSERT IGNORE INTO t_wx_account_binding
                (tenant_id, wx_openid, user_id, status, created_at, updated_at, is_deleted, version)
            SELECT tenant_id, wx_openid, id, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0
            FROM t_user
            WHERE wx_openid IS NOT NULL AND wx_openid <> '' AND is_deleted = 0
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if "t_wx_account_binding" in inspect(bind).get_table_names():
        op.drop_table("t_wx_account_binding")
