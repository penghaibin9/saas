"""add version column to aa grade identity head

Revision ID: 20260824_aa_grade_id_ver
Revises: 20260822_pr190_main_merge
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260824_aa_grade_id_ver"
down_revision = "20260822_pr190_main_merge"
branch_labels = None
depends_on = None

_TABLE_NAME = "t_aa_grade_identity_head"
_COLUMN_NAME = "version"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {column["name"] for column in insp.get_columns(_TABLE_NAME)}
    if _COLUMN_NAME not in columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column(
                _COLUMN_NAME,
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
                comment="乐观锁版本",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = {column["name"] for column in insp.get_columns(_TABLE_NAME)}
    if _COLUMN_NAME in columns:
        op.drop_column(_TABLE_NAME, _COLUMN_NAME)
