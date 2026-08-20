from __future__ import annotations

import inspect

from fastapi import FastAPI

from app.api.v1 import teacher_mobile_sequential as sequential_api
from app.api.v1 import todos as todos_api
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


def _openapi_paths(client: str) -> set[str]:
    # Validate the same resolved surface production exposes. FastAPI 0.141 keeps nested
    # APIRouter inclusions as lazy _IncludedRouter entries, so direct `.routes` traversal is
    # an implementation detail and can raise before the public routing contract is evaluated.
    app = FastAPI()
    app.include_router(todos_api.make_router(client), prefix="/api/v1")
    return set(app.openapi().get("paths", {}))


def test_t5_sequential_command_router_is_additive_under_teacher_mobile_only():
    teacher_paths = _openapi_paths("teacher-mobile")
    admin_paths = _openapi_paths("admin")
    student_paths = _openapi_paths("student-mini")

    assert "/api/v1/teacher-mobile/internship/exceptions/{exception_id}/handle" in teacher_paths
    assert "/api/v1/teacher-mobile/students" in teacher_paths
    assert "/api/v1/teacher-mobile/students/{student_id}/projection" in teacher_paths
    assert "/api/v1/admin/internship/exceptions/{exception_id}/handle" not in admin_paths
    assert "/api/v1/student-mini/internship/exceptions/{exception_id}/handle" not in student_paths
