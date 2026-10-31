"""合并补考学院审核与教材退款迁移终点；不修改业务表或数据。"""
from __future__ import annotations


revision = "20261031_merge_makeup_textbook"
down_revision = (
    "20261029_aa_makeup_review",
    "20261029_textbook_refund",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
