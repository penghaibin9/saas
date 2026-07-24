"""Expand：学院/专业/班级编码租户内唯一索引（前置重复检测失败则中止，不删不合并）。

Revision ID: 0132_org_code_unique_expand
Revises: 0131_internship_p2_compliance
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0132_org_code_unique_expand"
down_revision = "0131_internship_p2_compliance"
branch_labels = None
depends_on = None


def _assert_no_dups(bind, table: str, code_col: str, uk_name: str) -> None:
    rows = bind.execute(sa.text(
        f"""
        SELECT `{code_col}` AS code, COUNT(*) AS cnt
        FROM `{table}`
        WHERE is_deleted = 0
          AND `{code_col}` IS NOT NULL
          AND `{code_col}` <> ''
        GROUP BY `{code_col}`, tenant_id
        HAVING COUNT(*) > 1
        LIMIT 20
        """
    )).fetchall()
    if rows:
        sample = ", ".join(f"{r.code}×{r.cnt}" for r in rows[:5])
        raise RuntimeError(
            f"无法创建 {uk_name}：检测到重复编码（示例：{sample}）。"
            "请先用 /system/org-duplicate-codes 只读清单人工处理，本迁移不自动删除或合并。"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # 前置只读检查：按租户+编码查重
    for table, col, uk in (
        ("t_college", "code", "uk_college_tenant_code"),
        ("t_major", "code", "uk_major_tenant_code"),
        ("t_class", "class_code", "uk_class_tenant_code"),
    ):
        _assert_no_dups(bind, table, col, uk)

    # Expand：仅新增唯一索引；不删旧字段、不回填、不改空值策略
    # MySQL 允许多个 NULL，空编码不参与冲突
    op.create_index("uk_college_tenant_code", "t_college", ["tenant_id", "code"], unique=True)
    op.create_index("uk_major_tenant_code", "t_major", ["tenant_id", "code"], unique=True)
    op.create_index("uk_class_tenant_code", "t_class", ["tenant_id", "class_code"], unique=True)


def downgrade() -> None:
    op.drop_index("uk_class_tenant_code", table_name="t_class")
    op.drop_index("uk_major_tenant_code", table_name="t_major")
    op.drop_index("uk_college_tenant_code", table_name="t_college")
