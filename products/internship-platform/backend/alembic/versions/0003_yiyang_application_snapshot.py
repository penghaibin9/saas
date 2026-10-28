"""Yiyang C01/G02 complete internship-application snapshot fields.

Revision ID: ix0003
Revises: ix0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0003"
down_revision = "ix0002"
branch_labels = None
depends_on = None

_TABLE = "t_internship_application"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("company_credit_code", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("company_principal", sa.String(100), nullable=True))
    op.add_column(_TABLE, sa.Column("company_scale", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("company_phone", sa.String(64), nullable=True))
    op.add_column(_TABLE, sa.Column("company_email", sa.String(200), nullable=True))
    op.add_column(_TABLE, sa.Column("company_nature", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("company_industry", sa.String(100), nullable=True))
    op.add_column(_TABLE, sa.Column("company_registered_address", sa.String(300), nullable=True))
    op.add_column(_TABLE, sa.Column("company_postal_code", sa.String(20), nullable=True))
    op.add_column(_TABLE, sa.Column("company_province", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("company_city", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("company_district", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("internship_department", sa.String(100), nullable=True))
    op.add_column(_TABLE, sa.Column("work_content", sa.Text(), nullable=True))
    op.add_column(_TABLE, sa.Column("enterprise_mentor_name", sa.String(100), nullable=True))
    op.add_column(_TABLE, sa.Column("enterprise_mentor_phone", sa.String(64), nullable=True))
    op.add_column(_TABLE, sa.Column("position_category", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("work_country", sa.String(100), nullable=True))
    op.add_column(_TABLE, sa.Column("work_province", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("work_city", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("work_district", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("internship_start_date", sa.DateTime(), nullable=True))
    op.add_column(_TABLE, sa.Column("internship_end_date", sa.DateTime(), nullable=True))
    op.add_column(_TABLE, sa.Column("internship_mode", sa.String(30), nullable=True))
    op.add_column(_TABLE, sa.Column("major_match", sa.Boolean(), nullable=True))
    op.add_column(_TABLE, sa.Column("agreed_salary", sa.Numeric(12, 2), nullable=True))
    op.add_column(_TABLE, sa.Column("agreement_file_ids", sa.JSON(), nullable=True))
    op.add_column(
        _TABLE,
        sa.Column(
            "registry_verification_status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'UNVERIFIED'"),
        ),
    )
    op.add_column(_TABLE, sa.Column("registry_verification_provider", sa.String(80), nullable=True))
    op.add_column(_TABLE, sa.Column("registry_reference", sa.String(120), nullable=True))
    op.add_column(_TABLE, sa.Column("registry_verified_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_intern_application_credit_code",
        _TABLE,
        ["tenant_id", "company_credit_code", "is_deleted"],
    )
    op.create_index(
        "ix_intern_application_registry_status",
        _TABLE,
        ["tenant_id", "registry_verification_status", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_intern_application_registry_status", table_name=_TABLE)
    op.drop_index("ix_intern_application_credit_code", table_name=_TABLE)
    for name in (
        "registry_verified_at",
        "registry_reference",
        "registry_verification_provider",
        "registry_verification_status",
        "agreement_file_ids",
        "agreed_salary",
        "major_match",
        "internship_mode",
        "internship_end_date",
        "internship_start_date",
        "work_district",
        "work_city",
        "work_province",
        "work_country",
        "position_category",
        "enterprise_mentor_phone",
        "enterprise_mentor_name",
        "work_content",
        "internship_department",
        "company_district",
        "company_city",
        "company_province",
        "company_postal_code",
        "company_registered_address",
        "company_industry",
        "company_nature",
        "company_email",
        "company_phone",
        "company_scale",
        "company_principal",
        "company_credit_code",
    ):
        op.drop_column(_TABLE, name)
