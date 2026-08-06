"""包 5：学籍异动并发合同列（expectedVersion / currentTask / decisionVersion / idempotency）。

Revision ID: 20260806_aa_pkg5_concur
Revises: 20260806_gd_pkg9_archive_ver
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260806_aa_pkg5_concur"
down_revision = "20260806_gd_pkg9_archive_ver"
branch_labels = None
depends_on = None

# alembic_version.version_num 的正式合同为 VARCHAR(32)，迁移 ID 必须稳定落入该边界。
assert len(revision) <= 32

_TABLE = "t_aa_status_change"
_UK_IDEMPOTENCY = "uk_aa_status_change_idem"
_COLUMNS = {
    "expected_student_version": sa.Column(
        "expected_student_version", sa.Integer(), nullable=True,
        comment="发起时学生主档 version 快照；终审条件更新据此判定主档是否被并发改写",
    ),
    "current_task_id": sa.Column(
        "current_task_id", sa.BigInteger(), nullable=True,
        comment="当前节点已认领的 t_workflow_task.id；与审批同事务写入",
    ),
    "decision_version": sa.Column(
        "decision_version", sa.Integer(), nullable=False, server_default=sa.text("0"),
        comment="审批决定单调版本；客户端可传 expectedDecisionVersion 做乐观锁",
    ),
    "idempotency_key": sa.Column(
        "idempotency_key", sa.String(length=120), nullable=True,
        comment="发起幂等键；同租户唯一，重复提交返回既有异动单",
    ),
}


def _existing_columns(bind) -> set[str]:
    return {row["name"] for row in inspect(bind).get_columns(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260806_aa_pkg5_concur requires MySQL")
    if _TABLE not in set(inspect(bind).get_table_names()):
        return
    present = _existing_columns(bind)
    for name, column in _COLUMNS.items():
        if name not in present:
            op.add_column(_TABLE, column)
    indexes = {row["name"] for row in inspect(bind).get_indexes(_TABLE)}
    if _UK_IDEMPOTENCY not in indexes:
        # MySQL 唯一索引允许多行 NULL：历史异动单不回填幂等键，不会互相冲突。
        op.create_index(_UK_IDEMPOTENCY, _TABLE, ["tenant_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260806_aa_pkg5_concur requires MySQL")
    if _TABLE not in set(inspect(bind).get_table_names()):
        return
    indexes = {row["name"] for row in inspect(bind).get_indexes(_TABLE)}
    if _UK_IDEMPOTENCY in indexes:
        op.drop_index(_UK_IDEMPOTENCY, table_name=_TABLE)
    present = _existing_columns(bind)
    for name in reversed(list(_COLUMNS)):
        if name in present:
            op.drop_column(_TABLE, name)
