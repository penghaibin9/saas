"""Persist an immutable implementation acceptance summary.

Revision ID: 0111_immutable_acceptance_summary
Revises: 0110_change_impact_analysis

兼容说明：0001 历史迁移会导入运行时当前 metadata，空库升级时本列/唯一约束可能已
提前创建，故先探测再执行原始 DDL（同 0103/0104/0105 约定）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0111_immutable_acceptance_summary"
down_revision = "0110_change_impact_analysis"
branch_labels = None
depends_on = None

_TABLE = "t_system_implementation_project"


def _column_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _unique_constraint_names(table: str) -> set:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return set()
    return {uc["name"] for uc in sa.inspect(bind).get_unique_constraints(table)}


def upgrade() -> None:
    columns = _column_names(_TABLE)
    if "acceptance_digest" not in columns:
        op.add_column(_TABLE, sa.Column("acceptance_digest", sa.String(length=64), nullable=True))
    if "acceptance_summary" not in columns:
        op.add_column(_TABLE, sa.Column("acceptance_summary", sa.JSON(), nullable=True))
    if "uk_sys_impl_acceptance_digest" not in _unique_constraint_names(_TABLE):
        op.create_unique_constraint("uk_sys_impl_acceptance_digest", _TABLE, ["acceptance_digest"])


def downgrade() -> None:
    op.drop_constraint("uk_sys_impl_acceptance_digest", "t_system_implementation_project", type_="unique")
    op.drop_column("t_system_implementation_project", "acceptance_summary")
    op.drop_column("t_system_implementation_project", "acceptance_digest")
