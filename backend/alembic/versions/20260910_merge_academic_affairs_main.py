"""Merge the PR264 academic-affairs and current main migration heads.

This revision joins independent histories only; it performs no schema or data operation.
"""
from __future__ import annotations


revision = "20260910_merge_academic_affairs_main"
down_revision = (
    "20260909_aa_lab_schedule_room",
    "20260910_merge_commerce_news",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
