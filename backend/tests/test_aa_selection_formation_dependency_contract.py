"""B formation handoff: fail closed until Academic A exposes explicit task provenance."""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_formation_dependency as dependency


def test_missing_or_partial_provenance_is_a_dependency_blocker():
    for snapshot in (
        None,
        {},
        {"status": "PROVEN"},
        {"status": "PROVEN", "sourceProgramCourseId": "17"},
        {"status": "UNKNOWN", "sourceProgramCourseId": "17", "formationMode": "SELECTABLE"},
    ):
        with pytest.raises(AppException) as captured:
            dependency.require_proven_task_formation_snapshot(snapshot, teaching_task_id=31)
        exc = captured.value
        assert exc.code == "DATA_CONFLICT"
        assert dependency.BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE in str(exc.details)
        assert "31" in str(exc.details)


def test_weak_runtime_facts_never_substitute_for_program_course_provenance():
    weak_snapshot = {
        "status": "PROVEN",
        "courseId": "9",
        "classId": "12",
        "teachingTaskId": "31",
        "formationMode": "SELECTABLE",
    }
    with pytest.raises(AppException) as captured:
        dependency.require_proven_task_formation_snapshot(weak_snapshot, teaching_task_id=31)
    assert dependency.BLOCKER_FORMATION_PROVENANCE_UNAVAILABLE in str(captured.value.details)


def test_complete_provenance_is_normalized_without_reimplementing_a_policy():
    snapshot = dependency.require_proven_task_formation_snapshot(
        {
            "status": "proven",
            "sourceProgramCourseId": 17,
            "formationMode": "selectable",
            "courseId": 9,
            "classId": 12,
        },
        teaching_task_id=31,
    )
    assert snapshot == {
        "status": "PROVEN",
        "sourceProgramCourseId": "17",
        "formationMode": "SELECTABLE",
    }


def test_dependency_module_does_not_guess_or_claim_eligibility_policy():
    source = dependency.__file__
    text = open(source, encoding="utf-8").read()
    assert "selection_eligible" not in text
    assert "resolve_legacy_task_formation" not in text
    assert "ADMIN_FIXED" not in text
    assert "task majority" not in text.lower()
