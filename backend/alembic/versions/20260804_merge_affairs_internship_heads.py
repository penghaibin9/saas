"""Merge student-affairs repair and internship hardening migration heads.

Revision ID: 20260804_affairs_internship_merge
Revises: 0165_affairs_repair_job, 20260803_internship_hardening
Create Date: 2026-08-04
"""
from __future__ import annotations

revision = "20260804_affairs_internship_merge"
down_revision = ("0165_affairs_repair_job", "20260803_internship_hardening")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Schema changes are fully applied by both parent revisions."""


def downgrade() -> None:
    """Downgrading this merge revision restores the two parent heads."""
