"""Expand Program stable identity and formation provenance columns.

Revision ID: 20260817_aa_prog_expand
Revises: 20260816_merge_ctrl_intern_e

Expand-only migration: historical rows deliberately remain NULL.  Evidence-backed
backfill, NOT NULL tightening, and series/version uniqueness are separate phases
owned by the shared Program schema gate; this migration must not guess history.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260817_aa_prog_expand"
down_revision = "20260816_merge_ctrl_intern_e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_aa_program",
        sa.Column(
            "series_key",
            sa.String(length=64),
            nullable=True,
            comment="Stable Program series identity; historical rows require evidence-backed backfill",
        ),
    )
    op.add_column(
        "t_aa_program_course",
        sa.Column(
            "formation_mode",
            sa.String(length=30),
            nullable=True,
            comment="ProgramCourse formation provenance; historical rows require explicit source evidence",
        ),
    )


def downgrade() -> None:
    op.drop_column("t_aa_program_course", "formation_mode")
    op.drop_column("t_aa_program", "series_key")
