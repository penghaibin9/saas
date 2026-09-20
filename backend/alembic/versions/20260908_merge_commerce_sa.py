"""Merge module-commerce and student-affairs four-end migration heads.

Revision ID: 20260908_merge_commerce_sa
Revises: 20260906_fee_reduction_four_end, 20260908_module_commerce_m345

This revision performs no DDL. Both parent branches already own their schema
changes; the only purpose here is to restore one canonical Alembic head after
safely syncing current main into the module-commerce construction branch.
"""
from __future__ import annotations

revision = "20260908_merge_commerce_sa"
down_revision = (
    "20260906_fee_reduction_four_end",
    "20260908_module_commerce_m345",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
