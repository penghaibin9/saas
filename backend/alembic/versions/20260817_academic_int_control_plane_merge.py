"""Merge Academic INT and merged Control Plane/Internship migration lineages.

Revision ID: 20260817_acad_int_ctrl_merge
Revises: 20260816_acad_int_c1_att, 20260816_merge_ctrl_intern_e

Pure Alembic DAG convergence only.  Both parent lineages already own and test
their schema changes independently.  Program stable-series DDL must descend
from this revision in a later expand-only migration; it is intentionally absent
here so lineage convergence and schema evolution remain separately reviewable.
"""
from __future__ import annotations

revision = "20260817_acad_int_ctrl_merge"
down_revision = (
    "20260816_acad_int_c1_att",
    "20260816_merge_ctrl_intern_e",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
