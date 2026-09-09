"""Bind enterprise evaluation truth to the current formal placement.

Revision ID: 20260830_ix_eval_place
Revises: 20260829_pr236_main_merge
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260830_ix_eval_place"
down_revision = "20260829_pr236_main_merge"
branch_labels = None
depends_on = None

_TABLE = "t_internship_enterprise_eval"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260830_ix_eval_place requires MySQL")


def upgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    columns = {row["name"] for row in inspect(bind).get_columns(_TABLE)}
    for name in ("placement_snapshot_id", "enterprise_id", "position_id"):
        if name not in columns:
            op.add_column(_TABLE, sa.Column(name, sa.BigInteger(), nullable=True))
            op.create_index(f"ix_{_TABLE}_{name}", _TABLE, [name])

    # Existing rows are frozen against the placement that is current at migration time.
    # Future placement changes rotate current_placement_snapshot_id, so these rows stop matching.
    op.execute(sa.text("""
        UPDATE t_internship_enterprise_eval e
        JOIN t_internship_record r
          ON r.tenant_id=e.tenant_id AND r.id=e.internship_id AND r.is_deleted=0
        JOIN t_internship_placement_snapshot p
          ON p.tenant_id=r.tenant_id AND p.id=r.current_placement_snapshot_id
         AND p.record_id=r.id AND p.company_id=r.enterprise_id
         AND p.position_id=r.position_id AND p.batch_id=r.batch_id
        SET e.placement_snapshot_id=p.id,
            e.enterprise_id=r.enterprise_id,
            e.position_id=r.position_id
        WHERE e.is_deleted=0 AND e.placement_snapshot_id IS NULL
    """))


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    columns = {row["name"] for row in inspect(bind).get_columns(_TABLE)}
    indexes = {row["name"] for row in inspect(bind).get_indexes(_TABLE)}
    for name in ("position_id", "enterprise_id", "placement_snapshot_id"):
        index = f"ix_{_TABLE}_{name}"
        if index in indexes:
            op.drop_index(index, table_name=_TABLE)
        if name in columns:
            op.drop_column(_TABLE, name)
