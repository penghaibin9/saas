"""Merge W1 academic archive review with the current control/teacher head.

Revision ID: 20260821_aa_ctrl_merge
Revises: 20260821_aa_archive_review, 20260821_ctrl_teacher_merge

This is a topology-only migration. Both parent revisions own their schema changes;
this revision deliberately performs no DDL and restores one deployable Alembic head.
"""
from __future__ import annotations

revision = "20260821_aa_ctrl_merge"
down_revision = ("20260821_aa_archive_review", "20260821_ctrl_teacher_merge")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
