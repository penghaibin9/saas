"""真实演示沙箱基线保护索引。

Revision ID: aa_sandbox_baseline
Revises: aa_correction_material_r3
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_sandbox_baseline"
down_revision = "aa_correction_material_r3"
branch_labels = None
depends_on = None

TABLE = "t_sandbox_baseline"


def upgrade() -> None:
    if TABLE in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("row_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("tenant_id", "table_name", "row_id", name="uk_sandbox_baseline_row"),
    )
    op.create_index("ix_t_sandbox_baseline_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_t_sandbox_baseline_table_name", TABLE, ["table_name"])
    op.create_index("ix_t_sandbox_baseline_row_id", TABLE, ["row_id"])


def downgrade() -> None:
    if TABLE in inspect(op.get_bind()).get_table_names():
        op.drop_table(TABLE)
