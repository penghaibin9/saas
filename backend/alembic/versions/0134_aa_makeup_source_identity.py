"""补考/清考/缓考后续考试来源身份。

Revision ID: 0134_aa_makeup_source_identity
Revises: 0133_aa_roster_history
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0134_aa_makeup_source_identity"
down_revision = "0133_aa_roster_history"
branch_labels = None
depends_on = None

_TABLE = "t_acad_makeup"
_UNIQUE = "uk_acad_makeup_source_biz"
_INDEXES = {
    "ix_acad_makeup_teaching_task": ["tenant_id", "teaching_task_id"],
    "ix_acad_makeup_roster_version": ["tenant_id", "roster_version_id"],
}
_COLUMNS = {
    "source_biz_type": sa.Column("source_biz_type", sa.String(50), nullable=True),
    "source_biz_id": sa.Column("source_biz_id", sa.BigInteger(), nullable=True),
    "teaching_task_id": sa.Column("teaching_task_id", sa.BigInteger(), nullable=True),
    "teaching_class_id": sa.Column("teaching_class_id", sa.BigInteger(), nullable=True),
    "roster_version_id": sa.Column("roster_version_id", sa.BigInteger(), nullable=True),
}


def _table_names(bind):
    return set(inspect(bind).get_table_names())


def _column_names(bind):
    if _TABLE not in _table_names(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_columns(_TABLE)}


def _index_names(bind):
    if _TABLE not in _table_names(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_indexes(_TABLE)}


def _unique_names(bind):
    if _TABLE not in _table_names(bind):
        return set()
    return {row["name"] for row in inspect(bind).get_unique_constraints(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in _table_names(bind):
        return
    columns = _column_names(bind)
    for name, column in _COLUMNS.items():
        if name not in columns:
            op.add_column(_TABLE, column)

    indexes = _index_names(bind)
    for name, cols in _INDEXES.items():
        if name not in indexes:
            op.create_index(name, _TABLE, cols)

    if _UNIQUE not in _unique_names(bind) and _UNIQUE not in _index_names(bind):
        op.create_unique_constraint(
            _UNIQUE,
            _TABLE,
            ["tenant_id", "source_biz_type", "source_biz_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE not in _table_names(bind):
        return
    if _UNIQUE in _unique_names(bind) or _UNIQUE in _index_names(bind):
        op.drop_constraint(_UNIQUE, _TABLE, type_="unique")
    indexes = _index_names(bind)
    for name in _INDEXES:
        if name in indexes:
            op.drop_index(name, table_name=_TABLE)
    columns = _column_names(bind)
    for name in reversed(list(_COLUMNS)):
        if name in columns:
            op.drop_column(_TABLE, name)
