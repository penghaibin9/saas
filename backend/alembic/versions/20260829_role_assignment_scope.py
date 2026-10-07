"""Add stable five-level scope nodes to role assignments.

Revision ID: 20260829_role_assign_scope
Revises: 20260829_aa_grade_head_ver
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260829_role_assign_scope"
down_revision = "20260829_aa_grade_head_ver"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("t_role_assignment_scope"):
        return
    op.create_table(
        "t_role_assignment_scope",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("user_role_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("effective_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id", "user_role_id", "scope_type", "scope_id",
            name="uk_role_assignment_scope_node",
        ),
    )
    op.create_index("ix_t_role_assignment_scope_tenant_id", "t_role_assignment_scope", ["tenant_id"])
    op.create_index("ix_t_role_assignment_scope_user_role_id", "t_role_assignment_scope", ["user_role_id"])
    op.create_index("ix_t_role_assignment_scope_user_id", "t_role_assignment_scope", ["user_id"])
    op.create_index("ix_t_role_assignment_scope_role_code", "t_role_assignment_scope", ["role_code"])
    op.create_index(
        "idx_role_assignment_scope_user_role", "t_role_assignment_scope",
        ["tenant_id", "user_id", "role_code", "status"],
    )
    op.create_index(
        "idx_role_assignment_scope_resource", "t_role_assignment_scope",
        ["tenant_id", "scope_type", "scope_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("t_role_assignment_scope")
