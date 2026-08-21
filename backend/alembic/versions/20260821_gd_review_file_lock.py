"""W7.1 lock formal graduation review to canonical FileVersion.

Revision ID: 20260821_gd_review_file_lock
Revises: 20260820_teacher_emp_reco
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260821_gd_review_file_lock"
down_revision = "20260820_teacher_emp_reco"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("t_gd_review", sa.Column("material_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_review", sa.Column("file_version_id", sa.BigInteger(), nullable=True))
    op.add_column("t_gd_review", sa.Column("source_sha256", sa.String(length=64), nullable=True))
    op.add_column("t_gd_review", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_gd_review_tenant_file_version",
        "t_gd_review",
        ["tenant_id", "file_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_gd_review_tenant_material",
        "t_gd_review",
        ["tenant_id", "material_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_gd_review_tenant_material", table_name="t_gd_review")
    op.drop_index("ix_gd_review_tenant_file_version", table_name="t_gd_review")
    op.drop_column("t_gd_review", "started_at")
    op.drop_column("t_gd_review", "source_sha256")
    op.drop_column("t_gd_review", "file_version_id")
    op.drop_column("t_gd_review", "material_id")
