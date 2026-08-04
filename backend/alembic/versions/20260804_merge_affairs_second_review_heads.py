"""Merge student-affairs closeout with latest main change-management head.

Revision ID: 20260804_affairs_r2_merge
Revises: 0169_change_management, 20260804_affairs_final_merge
Create Date: 2026-08-04
"""
from __future__ import annotations

revision = "20260804_affairs_r2_merge"
down_revision = ("0169_change_management", "20260804_affairs_final_merge")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parent branches already contain their schema changes."""


def downgrade() -> None:
    """Downgrade restores the two parent heads without reversing schema."""
