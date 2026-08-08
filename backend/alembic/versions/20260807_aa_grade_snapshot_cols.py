"""补齐有效成绩策略快照与成绩变更申请表遗漏的公共列。

`0132_aa_effective_grade_policy_snapshot` 建表时把 CommonMixin 的 `version` 落下了，
`t_aa_grade_change_request` 则缺 `created_by/updated_by`。ORM 侧这些列一直存在，于是：

    任何一次正式成绩写入 → after_insert 钩子写策略快照 → INSERT 带 version 列
    → 真实库 1054 Unknown column 'version' → 500

测试库是 `metadata.create_all()` 建的，列齐全，所以测试全绿，问题只在跑过 alembic 的
真实库上出现——正是「迁移库与 ORM 库分裂」被测试掩盖的典型。这里按 ORM 定义补齐。

Revision ID: 20260807_aa_snap_cols
Revises: 20260807_aa_recog_ev
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260807_aa_snap_cols"
down_revision = "20260807_aa_recog_ev"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_SNAPSHOT = "t_aa_effective_grade_policy_snapshot"
_CHANGE_REQUEST = "t_aa_grade_change_request"


def _has_column(bind, table: str, column: str) -> bool:
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def _table_exists(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, _SNAPSHOT) and not _has_column(bind, _SNAPSHOT, "version"):
        op.add_column(_SNAPSHOT, sa.Column(
            "version", sa.Integer(), nullable=False, server_default="0",
            comment="乐观锁版本（CommonMixin），0132 建表时遗漏"))

    if _table_exists(bind, _CHANGE_REQUEST):
        for column in ("created_by", "updated_by"):
            if not _has_column(bind, _CHANGE_REQUEST, column):
                op.add_column(_CHANGE_REQUEST, sa.Column(column, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, _SNAPSHOT, "version"):
        op.drop_column(_SNAPSHOT, "version")
    for column in ("updated_by", "created_by"):
        if _has_column(bind, _CHANGE_REQUEST, column):
            op.drop_column(_CHANGE_REQUEST, column)
