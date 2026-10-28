"""Yiyang AP04 enterprise-to-college applicability scope.

Revision ID: ix0022
Revises: ix0021
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0022"
down_revision = "ix0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_enterprise_college_scope",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("company_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("college_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("scope_source", sa.String(30), nullable=False, server_default="MANUAL"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id", "company_id", "college_id",
            name="uk_ix_enterprise_college_scope",
        ),
    )
    op.create_index(
        "ix_ix_enterprise_college_scope_lookup",
        "t_internship_enterprise_college_scope",
        ["tenant_id", "college_id", "company_id", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ix_enterprise_college_scope_lookup",
        table_name="t_internship_enterprise_college_scope",
    )
    op.drop_table("t_internship_enterprise_college_scope")
