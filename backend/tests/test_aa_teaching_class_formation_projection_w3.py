"""A-W3/A-C4 TeachingClass initial formation projection contract."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest


def _core():
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_core_service as core
    return core


@pytest.mark.parametrize(
    ("formation_mode", "expected_class_type"),
    [
        ("ADMIN_FIXED", "ADMIN"),
        ("SELECTABLE", "SELECTION"),
        ("MERGED", "MERGED"),
        ("RETAKE", "RETAKE"),
        ("LAYERED", "LAYERED"),
    ],
)
def test_explicit_formation_drives_initial_teaching_class_type(formation_mode, expected_class_type):
    task = SimpleNamespace(formation_mode=formation_mode, is_merged=False)
    assert _core()._class_type(task) == expected_class_type


def test_legacy_task_without_formation_keeps_existing_admin_and_merged_behavior():
    core = _core()
    assert core._class_type(SimpleNamespace(is_merged=False)) == "ADMIN"
    assert core._class_type(SimpleNamespace(is_merged=True)) == "MERGED"


def test_invalid_explicit_formation_is_business_data_conflict_not_raw_500():
    from app.core.exceptions import AppException

    task = SimpleNamespace(id=811, formation_mode="ELECTIVE", is_merged=False)
    with pytest.raises(AppException) as exc:
        _core()._class_type(task)

    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    details = exc.value.details or {}
    assert details["blocker"] == "TEACHING_TASK_FORMATION_INVALID"
    assert details["teachingTaskId"] == "811"
    assert details["formationMode"] == "ELECTIVE"


@pytest.mark.parametrize(
    ("formation_mode", "class_type", "expected"),
    [
        ("ADMIN_FIXED", "ADMIN", True),
        ("MERGED", "MERGED", True),
        ("SELECTABLE", "SELECTION", False),
        ("RETAKE", "RETAKE", False),
        ("LAYERED", "LAYERED", False),
        (None, "ADMIN", True),
        (None, "MERGED", True),
        (None, "SELECTION", False),
        (None, "RETAKE", False),
        (None, "LAYERED", False),
    ],
)
def test_admin_roster_initialization_is_allowed_only_for_admin_semantics(
    formation_mode, class_type, expected
):
    task = SimpleNamespace(formation_mode=formation_mode, is_merged=class_type == "MERGED")
    teaching_class = SimpleNamespace(class_type=class_type)
    assert _core()._may_initialize_admin_roster(task, teaching_class) is expected


def test_selection_managed_legacy_class_cannot_fall_back_to_admin_roster():
    core = _core()
    task = SimpleNamespace(is_merged=False)
    teaching_class = SimpleNamespace(class_type="SELECTION")
    assert core._may_initialize_admin_roster(task, teaching_class) is False


def test_ensure_projection_calls_admin_roster_guard_before_initializing():
    source = inspect.getsource(_core().ensure_teaching_class_for_task)
    assert "_may_initialize_admin_roster(task, teaching_class)" in source
    assert source.index("_may_initialize_admin_roster(task, teaching_class)") < source.index(
        "student_ids = _administrative_roster(db, task)"
    )


def test_task_snapshot_carries_explicit_formation_but_keeps_legacy_empty():
    core = _core()
    batch = SimpleNamespace(id=91, term_id=202601)
    explicit = SimpleNamespace(
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
    legacy = SimpleNamespace(
        id=82,
        course_id=8,
        course_code="ADM101",
        course_name="行政班课程",
        class_id=17,
        class_name="软件2601",
        is_merged=False,
        merged_into_id=None,
    )

    explicit_snapshot = json.loads(core._task_snapshot(explicit, batch))
    legacy_snapshot = json.loads(core._task_snapshot(legacy, batch))
    assert explicit_snapshot["formationMode"] == "SELECTABLE"
    assert legacy_snapshot["formationMode"] == ""
