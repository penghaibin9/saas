"""INT contract for evidence-gated shared Program schema migration phases."""
from __future__ import annotations

import inspect

import pytest


def _gate():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_shared_schema_gate as gate
    return gate


def _series(**overrides):
    value = {
        "migrationPreflightSafe": True,
        "unresolvedProgramCount": 0,
        "blockerCounts": {},
        "seriesKeyBackfill": "PROVABLE_PREV_VERSION_ROOT_ONLY",
    }
    value.update(overrides)
    return value


def _formation(**overrides):
    value = {
        "migrationPreflightSafe": True,
        "unresolvedTaskCount": 0,
        "blockerCounts": {},
        "relationshipBlockerCounts": {},
        "programCourseFormationBackfill": "REQUIRES_EXPLICIT_PROVENANCE",
    }
    value.update(overrides)
    return value


def test_current_clean_task_inventory_allows_nullable_expand_but_not_programcourse_backfill():
    result = _gate().evaluate_shared_program_schema_gate(
        program_series_inventory=_series(),
        formation_inventory=_formation(),
    )
    assert result["inventoryEvidenceComplete"] is True
    assert result["nullableExpandAllowed"] is True
    assert result["programSeriesBackfillAllowed"] is True
    assert result["programCourseFormationBackfillAllowed"] is False
    assert result["sharedBackfillAllowed"] is False
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
    blocker = next(
        item for item in result["blockers"]
        if item["code"] == "PROGRAM_COURSE_FORMATION_BACKFILL_NOT_PROVEN"
    )
    assert blocker["evidence"]["taskFormationInventorySafe"] is True
    assert blocker["evidence"]["programCourseFormationBackfill"] == "REQUIRES_EXPLICIT_PROVENANCE"
    assert "ADMIN_FIXED" in blocker["howToResolve"]


def test_dirty_program_series_blocks_series_and_shared_backfill_without_blocking_nullable_expand():
    result = _gate().evaluate_shared_program_schema_gate(
        program_series_inventory=_series(
            migrationPreflightSafe=False,
            unresolvedProgramCount=3,
            blockerCounts={"PREDECESSOR_FORK": 1},
        ),
        formation_inventory=_formation(),
    )
    assert result["nullableExpandAllowed"] is True
    assert result["programSeriesBackfillAllowed"] is False
    assert result["sharedBackfillAllowed"] is False
    blocker = next(
        item for item in result["blockers"]
        if item["code"] == "PROGRAM_SERIES_BACKFILL_NOT_PROVEN"
    )
    assert blocker["evidence"]["unresolvedProgramCount"] == 3
    assert blocker["evidence"]["blockerCounts"] == {"PREDECESSOR_FORK": 1}
    assert "privileged baseline migration policy" in blocker["howToResolve"]


def test_hypothetical_explicit_programcourse_provenance_can_open_backfill_but_never_tighten():
    result = _gate().evaluate_shared_program_schema_gate(
        program_series_inventory=_series(),
        formation_inventory=_formation(
            programCourseFormationBackfill="EXPLICIT_PROVENANCE_PROVEN"
        ),
    )
    assert result["programSeriesBackfillAllowed"] is True
    assert result["programCourseFormationBackfillAllowed"] is True
    assert result["sharedBackfillAllowed"] is True
    assert result["blockers"] == []
    assert result["notNullTightenAllowed"] is False
    assert result["uniqueSeriesConstraintTightenAllowed"] is False
    assert result["postBackfillEvidenceRequired"] == [
        "ZERO_NULL_SERIES_KEY",
        "ZERO_NULL_FORMATION_MODE",
        "ZERO_SERIES_VERSION_COLLISION",
        "ZERO_FORMATION_PROVENANCE_MISMATCH",
        "N_MINUS_1_WRITERS_RETIRED",
    ]


def test_task_formation_blocker_stays_fail_closed_even_if_marker_claims_provenance():
    result = _gate().evaluate_shared_program_schema_gate(
        program_series_inventory=_series(),
        formation_inventory=_formation(
            migrationPreflightSafe=False,
            unresolvedTaskCount=1,
            blockerCounts={"FORMATION_SOURCE_MISSING": 1},
            programCourseFormationBackfill="EXPLICIT_PROVENANCE_PROVEN",
        ),
    )
    assert result["programCourseFormationBackfillAllowed"] is False
    assert result["sharedBackfillAllowed"] is False


@pytest.mark.parametrize(
    "series,formation,match",
    [
        (None, _formation(), "program_series_inventory"),
        (_series(), None, "formation_inventory"),
        ({"migrationPreflightSafe": "yes", "seriesKeyBackfill": "PROVABLE_PREV_VERSION_ROOT_ONLY"}, _formation(), "must be boolean"),
        (_series(), {"migrationPreflightSafe": True}, "programCourseFormationBackfill"),
    ],
)
def test_malformed_inventory_evidence_fails_closed(series, formation, match):
    with pytest.raises(ValueError, match=match):
        _gate().evaluate_shared_program_schema_gate(
            program_series_inventory=series,
            formation_inventory=formation,
        )


def test_gate_has_no_model_alembic_or_dispatcher_write_owner():
    source = inspect.getsource(_gate())
    assert "op.add_column" not in source
    assert "mapped_column" not in source
    assert "AaProgram(" not in source
    assert "AaProgramCourse(" not in source
    assert "get_sessionmaker" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
