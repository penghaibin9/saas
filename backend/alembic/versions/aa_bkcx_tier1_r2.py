"""补考重修缓考免修 Tier1 续工（R2）：t_aa_exemption 加列 archive_status（材料归档标记）。

三级施工卡「11-材料归档」§8：免修材料归档状态，nullable varchar(20)，默认 NOT_ARCHIVED，
历史行零回填（既有行 upgrade 时统一置默认值）。幂等：inspect 判列。

Revision ID: aa_bkcx_tier1_r2
Revises: aa_jxrw_tier1_r1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_bkcx_tier1_r2"
down_revision = "aa_jxrw_tier1_r1"
branch_labels = None
depends_on = None

TABLE = "t_aa_exemption"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    cols = _cols(bind)
    if "archive_status" not in cols:
        op.add_column(TABLE, sa.Column(
            "archive_status", sa.String(20), nullable=True, server_default="NOT_ARCHIVED",
            comment="免修材料归档标记 NOT_ARCHIVED/ARCHIVED（三级施工卡 11-材料归档 §8）"))


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    if "archive_status" in _cols(bind):
        op.drop_column(TABLE, "archive_status")
