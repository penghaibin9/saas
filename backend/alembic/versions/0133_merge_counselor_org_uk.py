"""merge counselor assignment branch with org code unique expand.

Revision ID: 0133_merge_counselor_org_uk
Revises: 0130_affairs_counselor_assignment, 0132_org_code_unique_expand
Create Date: 2026-07-25

仅合并迁移图，不新增或删除任何数据库结构。
"""
from __future__ import annotations

revision = "0133_merge_counselor_org_uk"
down_revision = ("0130_affairs_counselor_assignment", "0132_org_code_unique_expand")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
