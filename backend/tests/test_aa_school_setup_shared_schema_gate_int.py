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
        "totalRows": 2,
        "blockers": [],
        "proposedBackfill": [
            {"programId": 1, "tenantId": 1, "version": 1, "rootProgramId": 1, "seriesKey": "LEGACY-1"},
            {"programId": 2, "tenantId": 1, "version": 2, "rootProgramId": 1, "seriesKey": "LEGACY-1"},
        ],
    }
    value.update(overrides)
    return value


def _task_formation(**overrides):
    value = {
        "migrationPreflightSafe": True,
        "unresolvedTaskCount": 0,
        "blockerCounts": {},
        "relationshipBlockerCounts": {},
    }
    value.update(overrides)
    return value


def _program_course_formation(**overrides):
    value = {
        "migrationPreflightSafe": False,
        "unresolvedProgramCourseCount": 2,
        "blockerCounts": {"FORMATION_PROVENANCE_MISSING": 2},
        "programCourseFormationBackfill": "REQUIRES_EXPLICIT_PROVENANCE",
    }
    value.update(overrides)
    return value


def _evaluate(*, series=None, task=None, program_course=None):
    return _gate().evaluate_shared_program_schema_gate(
        program_series_inventory=_series() if series is None else series,
        task_formation_inventory=_task_formation() if task is None else task,
        program_course_formation_inventory=(
            _program_course_formation() if program_course is None else program_course
        ),
    )


def test_current_canonical_series_evidence_allows_nullable_expand_but_not_programcourse_backfill():
    result = _evaluate()
    assert result["inventoryEvidenceComplete"] is True
    assert result["nullableExpandAllowed"] is True
    assert result["programSeriesBackfillAllowed"] is True
    assert result["programSeriesBackfillProposal"] == _series()["proposedBackfill"]
    assert result["taskFormationEvidenceClean"] is True
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
    assert blocker["evidence"]["unresolvedProgramCourseCount"] == 2
    assert blocker["evidence"]["programCourseFormationBackfill"] == "REQUIRES_EXPLICIT_PROVENANCE"
    assert "TeachingTask 多数票" in blocker["howToResolve"]
    assert "ADMIN_FIXED" in blocker["howToResolve"]


def test_dirty_program_series_blocks_series_and_shared_backfill_and_exposes_no_partial_mapping():
    result = _evaluate(series=_series(
        migrationPreflightSafe=False,
        totalRows=3,
        blockers=[{
            "code": "PROGRAM_VERSION_FORK",
            "programIds": [1, 2, 3],
            "evidence": {"parentProgramId": 1},
            "howToResolve": "fix",
        }],
        proposedBackfill=[],
    ))
    assert result["nullableExpandAllowed"] is True
    assert result["programSeriesBackfillAllowed"] is False
    assert result["programSeriesBackfillProposal"] == []
    assert result["sharedBackfillAllowed"] is False
    blocker = next(
        item for item in result["blockers"]
        if item["code"] == "PROGRAM_SERIES_BACKFILL_NOT_PROVEN"
    )
    assert blocker["evidence"] == {
        "migrationPreflightSafe": False,
        "totalPrograms": 3,
        "blockerCount": 1,
        "blockerCodes": ["PROGRAM_VERSION_FORK"],
        "proposedBackfillCount": 0,
    }
    assert "privileged baseline migration policy" in blocker["howToResolve"]
    assert "migration 重算 series" in blocker["howToResolve"]


def test_dirty_task_runtime_formation_blocks_shared_backfill_independently_of_programcourse_provenance():
    result = _evaluate(
        task=_task_formation(
            migrationPreflightSafe=False,
            unresolvedTaskCount=1,
            blockerCounts={"FORMATION_SOURCE_MISSING": 1},
        ),
        program_course=_program_course_formation(
            migrationPreflightSafe=True,
            unresolvedProgramCourseCount=0,
            blockerCounts={},
            programCourseFormationBackfill="EXPLICIT_PROVENANCE_PROVEN",
        ),
    )
    assert result["programSeriesBackfillAllowed"] is True
    assert result["taskFormationEvidenceClean"] is False
    assert result["programCourseFormationBackfillAllowed"] is True
    assert result["sharedBackfillAllowed"] is False
    blocker = next(
        item for item in result["blockers"]
        if item["code"] == "TASK_FORMATION_EVIDENCE_NOT_CLEAN"
    )
    assert blocker["evidence"]["unresolvedTaskCount"] == 1


def test_explicit_programcourse_provenance_plus_canonical_series_and_clean_task_can_open_backfill_but_never_tighten():
    result = _evaluate(program_course=_program_course_formation(
        migrationPreflightSafe=True,
        unresolvedProgramCourseCount=0,
        blockerCounts={},
        programCourseFormationBackfill="EXPLICIT_PROVENANCE_PROVEN",
    ))
    assert result["programSeriesBackfillAllowed"] is True
    assert len(result["programSeriesBackfillProposal"]) == 2
    assert result["taskFormationEvidenceClean"] is True
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


def test_programcourse_marker_alone_cannot_override_its_own_dirty_inventory():
    result = _evaluate(program_course=_program_course_formation(
        migrationPreflightSafe=False,
        unresolvedProgramCourseCount=1,
        blockerCounts={"FORMATION_PROVENANCE_INCOMPLETE": 1},
        programCourseFormationBackfill="EXPLICIT_PROVENANCE_PROVEN",
    ))
    assert result["programCourseFormationBackfillAllowed"] is False
    assert result["sharedBackfillAllowed"] is False


def test_canonical_series_safe_report_requires_complete_unique_backfill_mapping():
    with pytest.raises(ValueError, match="every Program row"):
        _evaluate(series=_series(
            totalRows=3,
            proposedBackfill=_series()["proposedBackfill"],
        ))

    with pytest.raises(ValueError, match="duplicates programId"):
        duplicate = _series()["proposedBackfill"]
        _evaluate(series=_series(proposedBackfill=[duplicate[0], duplicate[0]]))

    with pytest.raises(ValueError, match="dirty report must not contain partial"):
        _evaluate(series=_series(
            migrationPreflightSafe=False,
            blockers=[{"code": "PROGRAM_PARENT_MISSING"}],
        ))


@pytest.mark.parametrize(
    "series,task,program_course,match",
    [
        (None, _task_formation(), _program_course_formation(), "program_series_inventory"),
        (_series(), None, _program_course_formation(), "task_formation_inventory"),
        (_series(), _task_formation(), None, "program_course_formation_inventory"),
        ({"migrationPreflightSafe": "yes", "totalRows": 0, "blockers": [], "proposedBackfill": []}, _task_formation(), _program_course_formation(), "must be boolean"),
        ({"migrationPreflightSafe": True, "totalRows": 0, "blockers": {}}, _task_formation(), _program_course_formation(), "proposedBackfill must be a list"),
        (_series(), {"migrationPreflightSafe": True, "unresolvedTaskCount": -1}, _program_course_formation(), "non-negative integer"),
        (_series(), _task_formation(), {"migrationPreflightSafe": True}, "programCourseFormationBackfill"),
    ],
)
def test_malformed_inventory_evidence_fails_closed(series, task, program_course, match):
    with pytest.raises(ValueError, match=match):
        _gate().evaluate_shared_program_schema_gate(
            program_series_inventory=series,
            task_formation_inventory=task,
            program_course_formation_inventory=program_course,
        )


def test_gate_has_no_model_alembic_dispatcher_or_graph_reimplementation_owner():
    source = inspect.getsource(_gate())
    assert "op.add_column" not in source
    assert "mapped_column" not in source
    assert "AaProgram(" not in source
    assert "AaProgramCourse(" not in source
    assert "get_sessionmaker" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "prev_version_id" not in source
    assert "VERSION_CYCLE" not in source
