"""Targeted contract for the Program expand-first schema migration."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import String

from app.models import AaProgram, AaProgramCourse
from app.modules.academic_affairs.services.academic_affairs_school_setup_shared_schema_gate import (
    evaluate_shared_program_schema_gate,
)


_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260817_aa_prog_expand.py"
)


def test_program_expand_migration_is_pinned_to_real_merge_head_and_nullable_only():
    source = _MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260817_aa_prog_expand"' in source
    assert 'down_revision = "20260816_merge_ctrl_intern_e"' in source
    assert '"series_key"' in source
    assert '"formation_mode"' in source
    assert source.count("nullable=True") == 2

    # Expand is intentionally data-neutral. Historical identity/provenance must
    # come from the inventory/backfill phase, never from migration guesses.
    assert "server_default" not in source
    assert "op.execute" not in source
    assert "UPDATE " not in source.upper()
    assert "create_unique_constraint" not in source
    assert "alter_column" not in source


def test_program_expand_columns_are_registered_in_orm_metadata_without_tightening():
    series = AaProgram.__table__.c.series_key
    formation = AaProgramCourse.__table__.c.formation_mode

    assert hasattr(AaProgram, "series_key")
    assert isinstance(series.type, String)
    assert series.type.length == 64
    assert series.nullable is True
    assert series.default is None
    assert series.server_default is None

    assert hasattr(AaProgramCourse, "formation_mode")
    assert isinstance(formation.type, String)
    assert formation.type.length == 30
    assert formation.nullable is True
    assert formation.default is None
    assert formation.server_default is None

    # Expand-first means metadata must not silently introduce a stricter contract
    # than the physical migration.  Series/version uniqueness is a later evidence-
    # gated phase, not an ORM-only constraint.
    assert not any(
        getattr(constraint, "name", None) == "uk_aa_program_series_version"
        for constraint in AaProgram.__table__.constraints
    )


def test_shared_gate_keeps_backfill_and_tightening_out_of_nullable_expand():
    result = evaluate_shared_program_schema_gate(
        program_series_inventory={
            "migrationPreflightSafe": True,
            "totalRows": 0,
            "blockers": [],
            "proposedBackfill": [],
        },
        task_formation_inventory={
            "migrationPreflightSafe": True,
            "unresolvedTaskCount": 0,
            "blockerCounts": {},
            "relationshipBlockerCounts": {},
        },
        program_course_formation_inventory={
            "migrationPreflightSafe": True,
            "unresolvedProgramCourseCount": 0,
            "blockerCounts": {},
            "programCourseFormationBackfill": "EXPLICIT_PROVENANCE_PROVEN",
        },
    )

    assert result["nullableExpandAllowed"] is True
    assert result["notNullTightenAllowed"] is False
    assert result["uniqueSeriesConstraintTightenAllowed"] is False
    assert result["expandColumns"] == [
        {
            "table": "t_aa_program",
            "column": "series_key",
            "nullable": True,
            "historicalDefault": None,
        },
        {
            "table": "t_aa_program_course",
            "column": "formation_mode",
            "nullable": True,
            "historicalDefault": None,
        },
    ]
