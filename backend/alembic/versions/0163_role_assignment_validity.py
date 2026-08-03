"""SYS-07：角色成员有效期与来源（扩展 t_user_role，不改原表结构）。

Revision ID: 0163_role_assignment_validity
Revises: 0162_tenant_capability_setting
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0163_role_assignment_validity"
down_revision = "0162_tenant_capability_setting"
branch_labels = None
depends_on = None


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("0163_role_assignment_validity requires MySQL")


def upgrade() -> None:
    _require_mysql()
    insp = inspect(op.get_bind())

    if not insp.has_table("t_role_assignment_validity"):
        op.create_table(
            "t_role_assignment_validity",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("user_role_id", sa.BigInteger(), nullable=False, comment="= t_user_role.id"),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("role_code", sa.String(64), nullable=False),
            sa.Column("effective_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), comment="空=长期有效"),
            sa.Column("source_type", sa.String(32), nullable=False, server_default="MANUAL"),
            sa.Column("source_id", sa.String(128)),
            sa.Column("reason", sa.String(500)),
            sa.Column("granted_by", sa.BigInteger()),
            sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("revoked_by", sa.BigInteger()),
            sa.Column("revoke_reason", sa.String(500)),
            sa.Column("last_reviewed_at", sa.DateTime()),
            sa.Column("last_reviewed_term", sa.String(64)),
            sa.Column("transferred_to_user_id", sa.BigInteger()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            mysql_engine="InnoDB",
        )
        op.create_index("ix_t_role_assignment_validity_tenant_id",
                        "t_role_assignment_validity", ["tenant_id"])
        op.create_index("ix_t_role_assignment_validity_user_id",
                        "t_role_assignment_validity", ["user_id"])
        op.create_index("ix_t_role_assignment_validity_role_code",
                        "t_role_assignment_validity", ["role_code"])
        op.create_unique_constraint("uk_role_assignment_validity",
                                    "t_role_assignment_validity", ["tenant_id", "user_role_id"])
        op.create_index("idx_role_validity_expires", "t_role_assignment_validity",
                        ["tenant_id", "status", "expires_at"])
        op.create_index("idx_role_validity_user_role", "t_role_assignment_validity",
                        ["tenant_id", "user_id", "role_code"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if insp.has_table("t_role_assignment_validity"):
        op.drop_table("t_role_assignment_validity")
