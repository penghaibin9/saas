"""E-A01 M6: finalize volunteer lock release/unlock contract.

Revision ID: 20260815_internship_e_m6
Revises: 20260815_internship_e_m5

The earlier M4 candidate used temporary ``last_released_*`` column names. V3 freezes the
canonical coordination fields as ``released_at`` / ``release_reason`` and requires explicit
student unlock-request evidence. This migration renames the candidate columns in-place and adds
only the two missing coordination fields; no second volunteer/application fact is introduced.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260815_internship_e_m6"
down_revision = "20260815_internship_e_m5"
branch_labels = None
depends_on = None

_TABLE = "t_internship_volunteer_group"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260815_internship_e_m6 requires MySQL")


def _columns() -> set[str]:
    insp = inspect(op.get_bind())
    return {column["name"] for column in insp.get_columns(_TABLE)} if insp.has_table(_TABLE) else set()


def _coalesce_and_drop(*, canonical: str, legacy: str) -> None:
    """Converge a dirty partial migration that contains both legacy and canonical columns."""
    op.execute(sa.text(
        f"UPDATE {_TABLE} SET {canonical} = COALESCE({canonical}, {legacy}) "
        f"WHERE {legacy} IS NOT NULL"
    ))
    op.drop_column(_TABLE, legacy)


def upgrade() -> None:
    _require_mysql()
    columns = _columns()
    if not columns:
        raise RuntimeError("t_internship_volunteer_group must exist before M6")

    if "last_released_at" in columns and "released_at" in columns:
        _coalesce_and_drop(canonical="released_at", legacy="last_released_at")
    elif "last_released_at" in columns:
        op.alter_column(
            _TABLE,
            "last_released_at",
            new_column_name="released_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
    elif "released_at" not in columns:
        op.add_column(_TABLE, sa.Column("released_at", sa.DateTime()))

    columns = _columns()
    if "last_release_reason" in columns and "release_reason" in columns:
        _coalesce_and_drop(canonical="release_reason", legacy="last_release_reason")
    elif "last_release_reason" in columns:
        op.alter_column(
            _TABLE,
            "last_release_reason",
            new_column_name="release_reason",
            existing_type=sa.String(500),
            existing_nullable=True,
        )
    elif "release_reason" not in columns:
        op.add_column(_TABLE, sa.Column("release_reason", sa.String(500)))

    columns = _columns()
    if "unlock_requested_at" not in columns:
        op.add_column(_TABLE, sa.Column("unlock_requested_at", sa.DateTime()))
    if "unlock_request_reason" not in columns:
        op.add_column(_TABLE, sa.Column("unlock_request_reason", sa.String(500)))


def downgrade() -> None:
    _require_mysql()
    columns = _columns()
    if "unlock_request_reason" in columns:
        op.drop_column(_TABLE, "unlock_request_reason")
    if "unlock_requested_at" in columns:
        op.drop_column(_TABLE, "unlock_requested_at")

    columns = _columns()
    if "release_reason" in columns and "last_release_reason" in columns:
        _coalesce_and_drop(canonical="last_release_reason", legacy="release_reason")
    elif "release_reason" in columns:
        op.alter_column(
            _TABLE,
            "release_reason",
            new_column_name="last_release_reason",
            existing_type=sa.String(500),
            existing_nullable=True,
        )

    columns = _columns()
    if "released_at" in columns and "last_released_at" in columns:
        _coalesce_and_drop(canonical="last_released_at", legacy="released_at")
    elif "released_at" in columns:
        op.alter_column(
            _TABLE,
            "released_at",
            new_column_name="last_released_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
