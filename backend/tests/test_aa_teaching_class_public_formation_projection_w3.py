"""A-C4 public TeachingClass formation projection wiring."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest


def _service():
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service
    return service


def test_public_teaching_class_projection_uses_formation_admin_roster_guard():
    source = inspect.getsource(_service().ensure_teaching_class_for_task)
    guard = "_core._may_initialize_admin_roster(task, teaching_class)"
    assert guard in source
    assert source.index(guard) < source.index(
        "student_ids = _core._administrative_roster(db, task)"
    )


def test_public_teaching_class_snapshot_carries_explicit_formation():
    task = SimpleNamespace(
        id=81,
        formation_mode="SELECTABLE",
        course_id=7,
        course_code="SEL101",
        course_name="公共选修",
        class_id=None,
        class_name=None,
        is_merged=False,
        merged_into_id=None,
    )
    batch = SimpleNamespace(id=91, term_id=202601)
    snapshot = json.loads(_service()._safe_task_snapshot(task, batch))
    assert snapshot["formationMode"] == "SELECTABLE"


def test_existing_teaching_class_matching_explicit_formation_is_accepted():
    service = _service()
    task = SimpleNamespace(id=811, formation_mode="SELECTABLE")
    teaching_class = SimpleNamespace(
        id=911,
        class_type="SELECTION",
        current_roster_version_id=1001,
    )
    assert service._guard_existing_class_formation(task, teaching_class) is None


def test_existing_teaching_class_formation_mismatch_fails_closed_with_evidence():
    from app.core.exceptions import AppException

    service = _service()
    task = SimpleNamespace(id=812, formation_mode="ADMIN_FIXED")
    teaching_class = SimpleNamespace(
        id=912,
        class_type="SELECTION",
        current_roster_version_id=1002,
    )
    with pytest.raises(AppException) as exc:
        service._guard_existing_class_formation(task, teaching_class)

    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    details = exc.value.details or {}
    assert details["blocker"] == "TEACHING_CLASS_FORMATION_MISMATCH"
    assert details["teachingTaskId"] == "812"
    assert details["teachingClassId"] == "912"
    assert details["formationMode"] == "ADMIN_FIXED"
    assert details["expectedClassType"] == "ADMIN"
    assert details["actualClassType"] == "SELECTION"
    assert details["currentRosterVersionId"] == "1002"


def test_legacy_task_without_explicit_formation_keeps_existing_class_compatibility():
    service = _service()
    task = SimpleNamespace(id=813)
    teaching_class = SimpleNamespace(
        id=913,
        class_type="SELECTION",
        current_roster_version_id=None,
    )
    assert service._guard_existing_class_formation(task, teaching_class) is None


def test_public_writer_checks_formation_drift_before_mutating_existing_class():
    source = inspect.getsource(_service().ensure_teaching_class_for_task)
    guard = "_guard_existing_class_formation(task, teaching_class)"
    first_mutation = "teaching_class.term_id = int(batch.term_id)"
    assert guard in source
    assert first_mutation in source
    assert source.index(guard) < source.index(first_mutation)
