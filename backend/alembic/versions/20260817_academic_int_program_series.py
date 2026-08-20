"""Add stable Program series identity after Academic/Control Plane convergence.

Revision ID: 20260817_acad_int_program_series
Revises: 20260817_acad_int_ctrl_merge

Historical Program rows deliberately remain NULL. This migration never guesses
series identity and performs no semantic backfill.

The series_key column is shared with A's nullable expand revision. Upgrade is
branch-order safe: create the column only when absent, then install the INT unique
series/version contract exactly once.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260817_acad_int_program_series"
down_revision = "20260817_acad_int_ctrl_merge"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _unique_names(table_name: str) -> set[str]:
    return {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _revision_is_current(revision_id: str) -> bool:
    row = op.get_bind().execute(
        sa.text("SELECT 1 FROM alembic_version WHERE version_num = :revision_id"),
        {"revision_id": revision_id},
    ).first()
    return row is not None


def upgrade() -> None:
    if "series_key" not in _columns("t_aa_program"):
        op.add_column(
            "t_aa_program",
            sa.Column(
                "series_key",
                sa.String(length=64),
                nullable=True,
                comment="Stable Program series identity; unresolved historical rows stay NULL",
            ),
        )

    if "uk_aa_program_series_version" not in _unique_names("t_aa_program"):
        op.create_unique_constraint(
            "uk_aa_program_series_version",
            "t_aa_program",
            ["tenant_id", "series_key", "version"],
        )


def downgrade() -> None:
    if "uk_aa_program_series_version" in _unique_names("t_aa_program"):
        op.drop_constraint("uk_aa_program_series_version", "t_aa_program", type_="unique")

    if (
        "series_key" in _columns("t_aa_program")
        and not _revision_is_current("20260817_aa_prog_expand")
    ):
        op.drop_column("t_aa_program", "series_key")
