"""A-C4 public TeachingClass formation projection wiring."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace


def test_public_teaching_class_projection_uses_formation_admin_roster_guard():
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

    source = inspect.getsource(service.ensure_teaching_class_for_task)
    guard = "_core._may_initialize_admin_roster(task, teaching_class)"
    assert guard in source
    assert source.index(guard) < source.index(
        "student_ids = _core._administrative_roster(db, task)"
    )


def test_public_teaching_class_snapshot_carries_explicit_formation():
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as service

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
    snapshot = json.loads(service._safe_task_snapshot(task, batch))
    assert snapshot["formationMode"] == "SELECTABLE"
