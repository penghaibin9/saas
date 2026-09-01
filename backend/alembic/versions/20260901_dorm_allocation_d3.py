"""D3 harden dorm allocation runtime constraints.

Revision ID: 20260901_dorm_allocation_d3
Revises: 20260901_orientation_flow_o2
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260901_dorm_allocation_d3"
down_revision = "20260901_orientation_flow_o2"
branch_labels = None
depends_on = None


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def upgrade() -> None:
    if _scalar("""
        SELECT COUNT(*) FROM (
          SELECT tenant_id, allocation_batch_id, bed_id
          FROM t_affairs_dorm_allocation_item
          WHERE is_deleted=0 AND bed_id IS NOT NULL
          GROUP BY tenant_id, allocation_batch_id, bed_id HAVING COUNT(*) > 1
        ) x
    """):
        raise RuntimeError("D3 preflight failed: duplicate bed proposals exist in one allocation batch")
    if _scalar("""
        SELECT COUNT(*) FROM t_affairs_dorm_allocation_batch
        WHERE status='PUBLISHED' AND published_at IS NULL
    """):
        raise RuntimeError("D3 preflight failed: published allocation batch lacks published_at")
    op.create_unique_constraint(
        "uk_dorm_alloc_item_bed",
        "t_affairs_dorm_allocation_item",
        ["tenant_id", "allocation_batch_id", "bed_id"],
    )
    op.create_check_constraint(
        "ck_dorm_alloc_batch_publish_time",
        "t_affairs_dorm_allocation_batch",
        "status <> 'PUBLISHED' OR published_at IS NOT NULL",
    )


def downgrade() -> None:
    runtime_rows = _scalar("""
        SELECT
          (SELECT COUNT(*) FROM t_affairs_dorm_allocation_batch
           WHERE status <> 'DRAFT' OR published_at IS NOT NULL)
          +
          (SELECT COUNT(*) FROM t_affairs_dorm_allocation_item)
          +
          (SELECT COUNT(*) FROM t_affairs_dorm_stay
           WHERE source_type='ALLOCATION')
    """)
    if runtime_rows:
        raise RuntimeError(
            "D3 downgrade blocked: allocation runtime data exists; archive/export it before downgrade"
        )
    op.drop_constraint(
        "ck_dorm_alloc_batch_publish_time",
        "t_affairs_dorm_allocation_batch",
        type_="check",
    )
    op.drop_constraint(
        "uk_dorm_alloc_item_bed",
        "t_affairs_dorm_allocation_item",
        type_="unique",
    )
