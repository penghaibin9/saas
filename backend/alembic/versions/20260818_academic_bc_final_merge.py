"""Merge Academic B/INT and Academic C final migration heads.

Revision ID: 20260818_acad_bc_final
Revises: 20260818_acad_main_int_merge, 20260818_merge_prog_grade_dl

Pure W5 integration convergence. Both parent heads are independently reviewed
additive lineages; this node intentionally performs no DDL and no data rewrite.
The exact source is emitted as W5 evidence so the final integration owner can
persist the byte-identical revision once the upstream PR merge order is fixed.
"""
from __future__ import annotations

revision = "20260818_acad_bc_final"
down_revision = (
    "20260818_acad_main_int_merge",
    "20260818_merge_prog_grade_dl",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
