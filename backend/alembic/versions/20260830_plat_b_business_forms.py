"""Add PLAT-B immutable business form definitions and versions.

Revision ID: 20260830_plat_b_forms
Revises: 20260829_plat_a_integrity
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260830_plat_b_forms"
down_revision = "20260829_plat_a_integrity"
branch_labels = None
depends_on = None

assert len(revision) <= 32


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("t_business_form_definition"):
        op.create_table(
            "t_business_form_definition",
            *_common_columns(),
            sa.Column("form_code", sa.String(length=100), nullable=False),
            sa.Column("form_name", sa.String(length=200), nullable=False),
            sa.Column("domain_code", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("active_version_id", sa.BigInteger(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "form_code", name="uk_business_form_definition_code",
            ),
        )
        op.create_index(
            "ix_t_business_form_definition_tenant_id",
            "t_business_form_definition", ["tenant_id"],
        )
        op.create_index(
            "ix_t_business_form_definition_active_version_id",
            "t_business_form_definition", ["active_version_id"],
        )
        op.create_index(
            "ix_business_form_definition_domain",
            "t_business_form_definition",
            ["tenant_id", "domain_code", "enabled", "is_deleted"],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("t_business_form_version"):
        op.create_table(
            "t_business_form_version",
            *_common_columns(),
            sa.Column("definition_id", sa.BigInteger(), nullable=False),
            sa.Column("form_code", sa.String(length=100), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("schema_hash", sa.String(length=64), nullable=False),
            sa.Column("schema_version", sa.String(length=40), nullable=False),
            sa.Column("supported_clients_json", sa.JSON(), nullable=False),
            sa.Column("policy_refs_json", sa.JSON(), nullable=False),
            sa.Column("domain_data_adapter", sa.String(length=100), nullable=False),
            sa.Column("domain_command_adapter", sa.String(length=100), nullable=False),
            sa.Column("schema_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
            sa.Column("effective_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("published_by", sa.BigInteger(), nullable=True),
            sa.Column("disabled_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "tenant_id", "definition_id", "version_no",
                name="uk_business_form_version_no",
            ),
            sa.UniqueConstraint(
                "tenant_id", "definition_id", "schema_hash",
                name="uk_business_form_version_hash",
            ),
        )
        op.create_index(
            "ix_t_business_form_version_tenant_id",
            "t_business_form_version", ["tenant_id"],
        )
        op.create_index(
            "ix_t_business_form_version_definition_id",
            "t_business_form_version", ["definition_id"],
        )
        op.create_index(
            "ix_business_form_version_status",
            "t_business_form_version",
            ["tenant_id", "form_code", "status", "effective_at", "is_deleted"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("t_business_form_version"):
        op.drop_table("t_business_form_version")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("t_business_form_definition"):
        op.drop_table("t_business_form_definition")
