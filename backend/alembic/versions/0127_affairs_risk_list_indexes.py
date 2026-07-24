"""学工风险列表热路径复合索引（第二轮 EXPLAIN：ORDER BY id 出现 filesort）。

候选依据（scripts/_r2_explain_risk.py）：
- 列表：tenant + is_deleted + ORDER BY id DESC LIMIT
- 统计：tenant + is_deleted + status / risk_level

Revision ID: 0127_affairs_risk_list_indexes
Revises: 0126_aa_grade_task_uniqueness_guard
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0127_affairs_risk_list_indexes"
down_revision = "0126_aa_grade_task_uniqueness_guard"
branch_labels = None
depends_on = None

INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_risk_tenant_active_id", "t_affairs_risk_record",
     ("tenant_id", "is_deleted", "id")),
    ("ix_risk_tenant_active_status", "t_affairs_risk_record",
     ("tenant_id", "is_deleted", "status")),
    ("ix_risk_tenant_active_level", "t_affairs_risk_record",
     ("tenant_id", "is_deleted", "risk_level")),
    ("ix_leave_tenant_active_status", "t_cs_leave",
     ("tenant_id", "is_deleted", "affairs_status")),
    ("ix_aid_apply_tenant_active_status", "t_affairs_aid_apply",
     ("tenant_id", "is_deleted", "status")),
)


def _has_index(inspector, table: str, name: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(ix.get("name") == name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for name, table, cols in INDEXES:
        if _has_index(inspector, table, name):
            continue
        op.create_index(name, table, list(cols), unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for name, table, _cols in reversed(INDEXES):
        if _has_index(inspector, table, name):
            op.drop_index(name, table_name=table)
