"""Merge Control Plane and Internship E migration lineages after main convergence.

Revision ID: 20260816_merge_ctrl_intern_e
Revises: 20260815_ctrl_identity_staging, 20260816_internship_e_m8

This is a pure Alembic DAG merge. Both parent migrations own independent schema
changes and have already been validated on their respective authority branches;
there is intentionally no DDL in this revision.
"""
from __future__ import annotations

revision = "20260816_merge_ctrl_intern_e"
down_revision = ("20260815_ctrl_identity_staging", "20260816_internship_e_m8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
