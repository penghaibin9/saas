"""Merge current main Program ancestry and Academic C GradeTask deadline lineage.

Revision ID: 20260818_merge_prog_grade_dl
Revises: 20260817_aa_prog_expand, 20260818_aa_grade_deadline

Pure Alembic DAG merge for PR #148 after PR #145/main convergence. Both parents
own independent additive schema changes; this revision intentionally performs no DDL.
"""
from __future__ import annotations

revision = "20260818_merge_prog_grade_dl"
down_revision = ("20260817_aa_prog_expand", "20260818_aa_grade_deadline")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
