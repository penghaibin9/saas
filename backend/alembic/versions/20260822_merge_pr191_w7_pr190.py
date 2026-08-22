"""Merge PR191 W7 review head with the PR190/main head.

Revision ID: 20260822_pr191_w7_main_merge
Revises: 20260822_gd_review_merge, 20260822_pr190_main_merge

Topology-only merge after latest main was synchronized into PR191. Both
parent revisions already own their schema changes; no DDL is repeated here.
"""
from __future__ import annotations

revision = "20260822_pr191_w7_main_merge"
down_revision = (
    "20260822_gd_review_merge",
    "20260822_pr190_main_merge",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
