"""Merge PR190 employment and latest-main academic archive heads.

Revision ID: 20260822_pr190_main_merge
Revises: 20260821_aa_ctrl_merge, 20260821_merge_emp_dest_ctrl_teacher

This is a topology-only migration created after PR190 synchronized with the
latest main branch. Both parent revisions own their schema changes; this
revision deliberately performs no DDL and restores one deployable Alembic head.
"""
from __future__ import annotations

revision = "20260822_pr190_main_merge"
down_revision = (
    "20260821_aa_ctrl_merge",
    "20260821_merge_emp_dest_ctrl_teacher",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
