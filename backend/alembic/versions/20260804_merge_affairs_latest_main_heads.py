"""Merge final student-affairs branch with latest main migration head.

Revision ID: 20260804_affairs_final_merge
Revises: 20260804_affairs_internship_merge, 73e91b9e47af
Create Date: 2026-08-04
"""
from __future__ import annotations

revision = '20260804_affairs_final_merge'
down_revision = ('20260804_affairs_internship_merge', '73e91b9e47af')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parent branches already contain their schema changes."""


def downgrade() -> None:
    """Downgrade restores the parent heads without reversing schema."""
