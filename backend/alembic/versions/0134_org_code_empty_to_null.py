"""组织编码空串规范为 NULL（已执行旧版 0132 的环境补丁）。

Revision ID: 0134_org_code_empty_to_null
Revises: 0133_merge_counselor_org_uk

不删行、不合并编码；仅 UPDATE '' → NULL，与唯一索引语义对齐。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0134_org_code_empty_to_null"
down_revision = "0133_merge_counselor_org_uk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table, col in (
        ("t_college", "code"),
        ("t_major", "code"),
        ("t_class", "class_code"),
    ):
        bind.execute(sa.text(
            f"UPDATE `{table}` SET `{col}` = NULL "
            f"WHERE `{col}` IS NOT NULL AND `{col}` = ''"
        ))


def downgrade() -> None:
    # 无法无损恢复哪些 NULL 曾是空串；保持 NULL。
    pass
