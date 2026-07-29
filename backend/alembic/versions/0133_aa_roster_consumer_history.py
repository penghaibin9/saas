"""R9 名单消费者快照支持退回重提历史。

现有 0129 表只允许每个消费者一条记录，无法保留成绩任务退回后重新提交时的名单版本证据。
本迁移增加 snapshot_version，并把唯一约束调整为“消费者 + 快照版本”。

Revision ID: 0133_aa_roster_history
Revises: 0132_aa_effective_grade_policy
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0133_aa_roster_history"
down_revision = "0132_aa_effective_grade_policy"
branch_labels = None
depends_on = None

_TABLE = "t_aa_roster_consumer_snapshot"
_OLD_UNIQUE = "uk_aa_roster_consumer"
_NEW_UNIQUE = "uk_aa_roster_consumer_version"
_HISTORY_INDEX = "ix_aa_roster_consumer_history"


def _tables(bind):
    return set(inspect(bind).get_table_names())


def _columns(bind):
    if _TABLE not in _tables(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_columns(_TABLE)}


def _indexes(bind):
    if _TABLE not in _tables(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_indexes(_TABLE)}


def _uniques(bind):
    if _TABLE not in _tables(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_unique_constraints(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in _tables(bind):
        return

    if "snapshot_version" not in _columns(bind):
        op.add_column(
            _TABLE,
            sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        )

    # 旧数据全部是每个消费者的首版冻结证据。
    op.execute(sa.text(
        f"UPDATE {_TABLE} SET snapshot_version = 1 "
        "WHERE snapshot_version IS NULL OR snapshot_version < 1"
    ))

    uniques = _uniques(bind)
    indexes = _indexes(bind)
    if _OLD_UNIQUE in uniques or _OLD_UNIQUE in indexes:
        op.drop_constraint(_OLD_UNIQUE, _TABLE, type_="unique")

    uniques = _uniques(bind)
    indexes = _indexes(bind)
    if _NEW_UNIQUE not in uniques and _NEW_UNIQUE not in indexes:
        op.create_unique_constraint(
            _NEW_UNIQUE,
            _TABLE,
            ["tenant_id", "consumer_type", "consumer_id", "snapshot_version"],
        )

    if _HISTORY_INDEX not in _indexes(bind):
        op.create_index(
            _HISTORY_INDEX,
            _TABLE,
            ["tenant_id", "consumer_type", "consumer_id", "status", "snapshot_version"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in _tables(bind):
        return

    # 旧结构只能保存一条记录。降级时保留每个消费者版本号最大的快照，其余历史证据会被删除。
    op.execute(sa.text(f"""
        DELETE older
        FROM {_TABLE} AS older
        INNER JOIN {_TABLE} AS newer
          ON newer.tenant_id = older.tenant_id
         AND newer.consumer_type = older.consumer_type
         AND newer.consumer_id = older.consumer_id
         AND newer.snapshot_version > older.snapshot_version
    """))

    if _HISTORY_INDEX in _indexes(bind):
        op.drop_index(_HISTORY_INDEX, table_name=_TABLE)

    uniques = _uniques(bind)
    indexes = _indexes(bind)
    if _NEW_UNIQUE in uniques or _NEW_UNIQUE in indexes:
        op.drop_constraint(_NEW_UNIQUE, _TABLE, type_="unique")

    if "snapshot_version" in _columns(bind):
        op.drop_column(_TABLE, "snapshot_version")

    uniques = _uniques(bind)
    indexes = _indexes(bind)
    if _OLD_UNIQUE not in uniques and _OLD_UNIQUE not in indexes:
        op.create_unique_constraint(
            _OLD_UNIQUE,
            _TABLE,
            ["tenant_id", "consumer_type", "consumer_id"],
        )
