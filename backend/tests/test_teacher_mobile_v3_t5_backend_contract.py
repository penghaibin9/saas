from __future__ import annotations

import inspect

from app.api.v1 import teacher_mobile_sequential as sequential_api
from app.api.v1 import teacher_mobile_students as teacher_mobile_router
from app.modules.internship.services import internship_service


def test_t5_attendance_exception_command_is_atomic_single_object_and_conflict_guarded():
    source = inspect.getsource(internship_service.handle_attendance_exception)
    assert "versioned_update" in source
    assert "expected_version" in source
    assert 'if c.status == "COMPLETED"' in source
    assert 'AppException("DATA_CONFLICT"' in source
    assert 'extra_where=(AttendanceException.status != "COMPLETED",)' in source
    assert "_rec_in_scope(_current_scope(user)" in source
    assert "for exception_id in" not in source
    assert "exception_ids" not in source


def test_t5_attendance_exception_action_set_stays_canonical():
    source = inspect.getsource(internship_service.handle_attendance_exception)
    assert '("REASONABLE", "ABNORMAL", "TO_RISK")' in source
    assert 'action == "TO_RISK"' in source
    assert 'todo_done(db, biz_id=c.id' in source


def test_t5_teacher_mobile_adapter_requires_exact_queue_version_and_delegates_to_canonical_command():
    source = inspect.getsource(sequential_api.handle_attendance_exception)
    body_source = inspect.getsource(sequential_api.AttendanceExceptionHandleBody)
    module_source = inspect.getsource(sequential_api)

    assert "expectedVersion: int" in body_source
    assert "internship_service.handle_attendance_exception" in source
    assert "expected_version=body.expectedVersion" in source
    assert "user=user" in source
    assert "require_staff" in module_source
    assert 'require_module("internship")' in module_source
    assert "for " not in source
    assert "Promise" not in source


def test_t5_sequential_command_router_is_additive_under_teacher_mobile_only():
    paths = {route.path for route in teacher_mobile_router.router.routes}
    assert "/internship/exceptions/{exception_id}/handle" in paths
    assert "/students" in paths
    assert "/students/{student_id}/projection" in paths
