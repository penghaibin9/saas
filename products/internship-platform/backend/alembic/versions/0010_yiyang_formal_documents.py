"""Yiyang C08/G17 formal printable documents.

Revision ID: ix0010
Revises: ix0009
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ix0010"
down_revision = "ix0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_internship_formal_document",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("internship_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("file_id", sa.String(64), nullable=True),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("generated_by_user_id", sa.String(64), nullable=True),
        sa.Column("generated_by_name", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="GENERATED"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint(
            "tenant_id", "internship_id", "document_type", "document_version",
            name="uk_ix_formal_document_version",
        ),
    )
    op.create_index(
        "ix_ix_formal_document_lookup",
        "t_internship_formal_document",
        ["tenant_id", "internship_id", "document_type", "status"],
    )
    op.create_index(
        "ix_t_internship_formal_document_internship_id",
        "t_internship_formal_document",
        ["internship_id"],
    )
    op.create_index(
        "ix_t_internship_formal_document_student_id",
        "t_internship_formal_document",
        ["student_id"],
    )
    op.create_index(
        "ix_t_internship_formal_document_batch_id",
        "t_internship_formal_document",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_table("t_internship_formal_document")
