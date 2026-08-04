"""merge academic-affairs P0 policy/correction and current main heads

Revision ID: 20260804_merge_aa_p0_main_heads
Revises: 0173_disaster_recovery, 0170_aa_grade_policy_correction
"""
from __future__ import annotations

revision = "20260804_merge_aa_p0_main_heads"
down_revision = ("0173_disaster_recovery", "0170_aa_grade_policy_correction")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
