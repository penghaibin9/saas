"""Record the installed snapshot that a change project inherits.

Revision ID: 0110_change_impact_analysis
Revises: 0109_implementation_permissions

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时本列/索引可能已提前
创建，故先探测再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0110_change_impact_analysis"
down_revision = "0109_implementation_permissions"
branch_labels = None
depends_on = None

_TABLE = "t_system_implementation_project"


def _column_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    if "change_source_installation_id" not in _column_names(_TABLE):
        op.add_column(
            _TABLE,
            sa.Column("change_source_installation_id", sa.BigInteger(), nullable=True),
        )
    if "ix_t_system_implementation_project_change_source" not in _index_names(_TABLE):
        op.create_index(
            "ix_t_system_implementation_project_change_source",
            _TABLE,
            ["change_source_installation_id"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_t_system_implementation_project_change_source",
        table_name=_TABLE,
    )
    op.drop_column(_TABLE, "change_source_installation_id")
