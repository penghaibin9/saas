"""Merge PR 236 and latest-main migration heads.

Revision ID: 20260829_pr236_main_merge
Revises: 20260824_aa_grade_id_ver, 20260829_aa_bypass_audit_cols
Create Date: 2026-08-29

This topology-only revision restores the repository single-head invariant after
syncing the latest main branch into PR 236. Both parent schema migrations retain
their own upgrade and downgrade behavior.
"""
from __future__ import annotations

revision = "20260829_pr236_main_merge"
down_revision = (
    "20260824_aa_grade_id_ver",
    "20260829_aa_bypass_audit_cols",
)
branch_labels = None
depends_on = None

assert len(revision) <= 32


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
