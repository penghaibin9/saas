"""Merge Internship V8 and latest-main PR239/PR240 migration heads.

Revision ID: 20260830_merge_ix_pr239
Revises: 20260830_merge_ix_plat_c, 20260830_pr239_240_merge
"""
from __future__ import annotations


revision = "20260830_merge_ix_pr239"
down_revision = ("20260830_merge_ix_plat_c", "20260830_pr239_240_merge")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the two already-applied additive migration lines."""


def downgrade() -> None:
    """Split back to the two parent heads without changing schema."""
