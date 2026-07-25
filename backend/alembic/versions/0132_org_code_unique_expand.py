"""Expand：学院/专业/班级编码租户内唯一索引（前置重复检测失败则中止，不删不合并）。

Revision ID: 0132_org_code_unique_expand
Revises: 0131_internship_p2_compliance

空编码策略：建索引前将 '' 规范为 NULL（多 NULL 不冲突）；不删除行、不合并编码。
若本 revision 已在旧版（未规范空串）环境下执行过，请继续执行 0134_org_code_empty_to_null。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


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


def _normalize_empty_to_null(bind, table: str, code_col: str) -> None:
    """空串 → NULL，使唯一索引与「空编码不参与冲突」语义一致。不删行。"""
    bind.execute(sa.text(
        f"UPDATE `{table}` SET `{code_col}` = NULL "
        f"WHERE `{code_col}` IS NOT NULL AND `{code_col}` = ''"
    ))


def _create_uk_if_missing(bind, table: str, name: str, cols: list[str]) -> None:
    insp = inspect(bind)
    existing = {i["name"] for i in insp.get_indexes(table)}
    if name in existing:
        return
    op.create_index(name, table, cols, unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    specs = (
        ("t_college", "code", "uk_college_tenant_code", ["tenant_id", "code"]),
        ("t_major", "code", "uk_major_tenant_code", ["tenant_id", "code"]),
        ("t_class", "class_code", "uk_class_tenant_code", ["tenant_id", "class_code"]),
    )
    for table, col, uk, cols in specs:
        _assert_no_dups(bind, table, col, uk)
        _normalize_empty_to_null(bind, table, col)
        _create_uk_if_missing(bind, table, uk, cols)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for name, table in (
        ("uk_class_tenant_code", "t_class"),
        ("uk_major_tenant_code", "t_major"),
        ("uk_college_tenant_code", "t_college"),
    ):
        if name in {i["name"] for i in insp.get_indexes(table)}:
            op.drop_index(name, table_name=table)
