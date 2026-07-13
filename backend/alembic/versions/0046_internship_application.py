"""Internship formal application ledger.

Revision ID: 0046_internship_application
Revises: 0045_gd_production_integrity
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0046_internship_application"
down_revision = "0045_gd_production_integrity"
branch_labels = None
depends_on = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _has(bind, table: str) -> bool:
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_application"):
        return
    op.create_table(
        "t_internship_application",
        sa.Column("id", BIGINT_PK, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("record_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=True),
        sa.Column("application_type", sa.String(32), nullable=False),
        sa.Column("volunteer_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("position_name", sa.String(100), nullable=True),
        sa.Column("work_address", sa.String(300), nullable=True),
        sa.Column("contact_name", sa.String(100), nullable=True),
        sa.Column("contact_phone", sa.String(64), nullable=True),
        sa.Column("evidence_file_id", sa.String(64), nullable=True),
        sa.Column("application_note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "record_id", "volunteer_no",
                            name="uk_intern_application_record_volunteer"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    for col in ("tenant_id", "record_id", "student_id", "batch_id", "application_type",
                "position_id", "status"):
        op.create_index(f"ix_t_internship_application_{col}", "t_internship_application", [col])


def downgrade() -> None:
    bind = op.get_bind()
    if _has(bind, "t_internship_application"):
        for idx in inspect(bind).get_indexes("t_internship_application"):
            op.drop_index(idx["name"], table_name="t_internship_application")
        op.drop_table("t_internship_application")
