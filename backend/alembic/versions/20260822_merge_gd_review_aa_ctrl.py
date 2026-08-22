"""Merge W7 graduation review closure with the current main Alembic head.

Revision ID: 20260822_gd_review_merge
Revises: 20260821_aa_ctrl_merge, 20260822_gd_review_closure

W7.1 was authored on the PR191 branch-local head while main independently advanced
through the academic/control/teacher merge chain. This topology-only revision joins
both already-applied histories without repeating DDL and restores one deployable head.
"""
from __future__ import annotations

revision = "20260822_gd_review_merge"
down_revision = ("20260821_aa_ctrl_merge", "20260822_gd_review_closure")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
