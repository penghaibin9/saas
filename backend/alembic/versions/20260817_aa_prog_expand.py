"""Expand Program stable identity and formation provenance columns.

Revision ID: 20260817_aa_prog_expand
Revises: 20260816_merge_ctrl_intern_e

Expand-only migration: historical rows deliberately remain NULL. Evidence-backed
backfill, NOT NULL tightening, and series/version uniqueness are separate phases
owned by the shared Program schema gate; this migration must not guess history.

This revision is also descendant-safe when Academic INT has already materialized
one or both shared columns. It only creates missing nullable columns and never
silently widens/narrows or backfills an existing shared schema.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260817_aa_prog_expand"
down_revision = "20260816_merge_ctrl_intern_e"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _check_names(table_name: str) -> set[str]:
    return {
        check.get("name")
        for check in sa.inspect(op.get_bind()).get_check_constraints(table_name)
        if check.get("name")
    }


def _unique_names(table_name: str) -> set[str]:
    return {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    if "series_key" not in _columns("t_aa_program"):
        op.add_column(
            "t_aa_program",
            sa.Column(
                "series_key",
                sa.String(length=64),
                nullable=True,
                comment="Stable Program series identity; historical rows require evidence-backed backfill",
            ),
        )

    if "formation_mode" not in _columns("t_aa_program_course"):
        op.add_column(
            "t_aa_program_course",
            sa.Column(
                "formation_mode",
                sa.String(length=30),
                nullable=True,
                comment="ProgramCourse formation provenance; historical rows require explicit source evidence",
            ),
        )


def downgrade() -> None:
    # If the INT branch still owns the stricter shared constraints, keep the shared
    # columns in place. Standalone A downgrades still remove exactly what A added.
    if (
        "formation_mode" in _columns("t_aa_program_course")
        and "ck_aa_program_course_formation_mode" not in _check_names("t_aa_program_course")
    ):
        op.drop_column("t_aa_program_course", "formation_mode")

    if (
        "series_key" in _columns("t_aa_program")
        and "uk_aa_program_series_version" not in _unique_names("t_aa_program")
    ):
        op.drop_column("t_aa_program", "series_key")
