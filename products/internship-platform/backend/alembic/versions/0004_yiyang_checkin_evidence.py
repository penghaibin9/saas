"""Yiyang C02/G05-G08 checkin evidence, local timezone and exemption.

Revision ID: ix0004
Revises: ix0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0004"
down_revision = "ix0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "t_internship_checkin"
    op.add_column(table, sa.Column("watermarked_file_id", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("evidence_sha256", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("watermarked_sha256", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("watermark_text", sa.String(500), nullable=True))
    op.add_column(table, sa.Column("timezone_name", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("timezone_offset_minutes", sa.Integer(), nullable=True))
    op.add_column(table, sa.Column("coordinate_system", sa.String(20), nullable=True))
    op.add_column(table, sa.Column("location_provider", sa.String(50), nullable=True))
    op.add_column(table, sa.Column("country_region", sa.String(100), nullable=True))
    op.create_index("ix_checkin_watermarked_file", table, ["tenant_id", "watermarked_file_id"])

    op.create_table(
        "t_internship_checkin_exemption",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "active_pending_internship_id",
            sa.BigInteger(),
            sa.Computed(
                "CASE WHEN is_deleted = 0 AND status = 'PENDING' THEN internship_id ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("evidence_file_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("apply_by_name", sa.String(100), nullable=True),
        sa.Column("review_by_name", sa.String(100), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "active_pending_internship_id",
            name="uk_ix_checkin_exemption_active_pending",
        ),
    )
    op.create_index(
        "ix_t_internship_checkin_exemption_tenant_id",
        "t_internship_checkin_exemption",
        ["tenant_id"],
    )
    op.create_index(
        "ix_t_internship_checkin_exemption_internship_id",
        "t_internship_checkin_exemption",
        ["internship_id"],
    )
    op.create_index(
        "ix_t_internship_checkin_exemption_student_id",
        "t_internship_checkin_exemption",
        ["student_id"],
    )
    op.create_index(
        "ix_t_internship_checkin_exemption_batch_id",
        "t_internship_checkin_exemption",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_checkin_exemption")
    table = "t_internship_checkin"
    op.drop_index("ix_checkin_watermarked_file", table_name=table)
    for column in (
        "country_region",
        "location_provider",
        "coordinate_system",
        "timezone_offset_minutes",
        "timezone_name",
        "watermark_text",
        "watermarked_sha256",
        "evidence_sha256",
        "watermarked_file_id",
    ):
        op.drop_column(table, column)
