"""补齐学籍修读记录的培养方案版本引用列。

Revision ID: 20260804_aa_enrollment_program
Revises: 20260804_merge_aa_p0_main_heads
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260804_aa_enrollment_program"
down_revision = "20260804_merge_aa_p0_main_heads"
branch_labels = None
depends_on = None

_TABLE = "academic_enrollments"
_COLUMN = "program_version_id"
_INDEX = "ix_academic_enrollments_program_version_id"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260804_aa_enrollment_program requires MySQL")


def upgrade() -> None:
    """让迁移链与当前 AcademicEnrollment ORM 映射保持一致。"""
    _require_mysql()
    bind = op.get_bind()
    inspector = inspect(bind)
    if _TABLE not in set(inspector.get_table_names()):
        return

    columns = {item["name"] for item in inspector.get_columns(_TABLE)}
    if _COLUMN not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.BigInteger(),
                nullable=True,
                comment="学生当前适用的培养方案版本ID",
            ),
        )

    indexes = {item["name"] for item in inspect(bind).get_indexes(_TABLE)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    inspector = inspect(bind)
    if _TABLE not in set(inspector.get_table_names()):
        return

    indexes = {item["name"] for item in inspector.get_indexes(_TABLE)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE)

    columns = {item["name"] for item in inspect(bind).get_columns(_TABLE)}
    if _COLUMN in columns:
        op.drop_column(_TABLE, _COLUMN)
