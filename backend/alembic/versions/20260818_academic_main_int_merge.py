"""Merge Academic A mainline and sealed INT shared-schema lineages.

Revision ID: 20260818_acad_main_int_merge
Revises: 20260817_aa_prog_expand, 20260818_acad_int_task_pc_prov

Pure Alembic DAG convergence. Both parent branches own their schema/runtime
semantics independently; descendant-safe shared DDL in those parents guarantees
fresh databases and already-upgraded branch databases converge without guessed
backfill or duplicate-column creation.
"""
from __future__ import annotations

revision = "20260818_acad_main_int_merge"
down_revision = (
    "20260817_aa_prog_expand",
    "20260818_acad_int_task_pc_prov",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
