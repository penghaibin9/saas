"""Merge the PR239 academic-chain and PR240 platform migration heads.

Revision ID: 20260830_pr239_240_merge
Revises: 20260830_plat_c_lifecycle, 20260830_role_scope_collation
"""
from __future__ import annotations


revision = "20260830_pr239_240_merge"
down_revision = (
    "20260830_plat_c_lifecycle",
    "20260830_role_scope_collation",
)
branch_labels = None
depends_on = None

assert len(revision) <= 32


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
