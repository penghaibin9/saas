"""合并并行 Alembic head：教务 Bug 修复(0122) + 实习 batch_id(0123)。

两份迁移均 Revises 0121（并行会话产物）。本文件仅空合并，不改业务结构。
若上线环境尚无 0123，请先应用实习侧迁移，或与实习负责人确认合并顺序。

Revision ID: 0124_merge_aa_bugfix_and_internship
Revises: 0122_aa_bugfix_credit_grade_uk, 0123_internship_batch_id_not_null
"""
from __future__ import annotations

revision = "0124_merge_aa_bugfix_and_internship"
down_revision = ("0122_aa_bugfix_credit_grade_uk", "0123_internship_batch_id_not_null")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
