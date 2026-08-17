"""Add stable Program series identity after Academic/Control Plane convergence.

Revision ID: 20260817_acad_int_program_series
Revises: 20260817_acad_int_ctrl_merge

Historical Program rows deliberately remain NULL.  This migration never guesses
series identity and performs no semantic backfill.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260817_acad_int_program_series"
down_revision = "20260817_acad_int_ctrl_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_aa_program",
        sa.Column(
            "series_key",
            sa.String(length=64),
            nullable=True,
            comment="Stable Program series identity; unresolved historical rows stay NULL",
        ),
    )
    op.create_unique_constraint(
        "uk_aa_program_series_version",
        "t_aa_program",
        ["tenant_id", "series_key", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uk_aa_program_series_version", "t_aa_program", type_="unique")
    op.drop_column("t_aa_program", "series_key")
