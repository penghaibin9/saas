from __future__ import annotations

import inspect

import pytest
from fastapi import FastAPI

from app.api.v1 import todos as todos_api
from app.core.exceptions import AppException
from app.services import teacher_mobile_student_keyset_service as student_svc


def _sample_cursor(**overrides):
    payload = {
        "v": 1,
        "kind": "teacherStudents",
        "filterHash": "students-hash",
        "asOf": "2026-08-20T00:00:00.000000",
        "studentNo": "20260001",
        "id": 17,
        "total": 31,
    }
    payload.update(overrides)
    return student_svc._encode_cursor(payload)


def test_t3_my_students_cursor_is_signed_and_filter_bound():
    cursor = _sample_cursor()
    decoded = student_svc._decode_cursor(cursor, expected_filter_hash="students-hash")
    assert decoded["studentNo"] == "20260001"
    assert decoded["id"] == 17
    assert decoded["total"] == 31
    assert cursor.count(".") == 1

    with pytest.raises(AppException):
        student_svc._decode_cursor(cursor, expected_filter_hash="different-filter")

    body, signature = cursor.split(".", 1)
    replacement = "A" if body[0] != "A" else "B"
    with pytest.raises(AppException):
        student_svc._decode_cursor(replacement + body[1:] + "." + signature,
                                   expected_filter_hash="students-hash")


def test_t3_my_students_is_true_keyset_search_and_class_filter_cannot_bypass_scope():
    source = inspect.getsource(student_svc.list_continuous)
    module_source = inspect.getsource(student_svc)

    assert ".offset(" not in module_source
    assert ".limit(size + 1)" in source
    assert "scope = teacher_guard.resolve_teacher_scope(user)" in source
    assert "compile_teacher_student_visibility(user, student.id, scope=scope)" in source
    assert "object_visibility" in source
    assert "student.class_id == normalized_class_id" in source
    assert "student.student_no.like" in source
    assert "student.real_name.like" in source
    assert "student.student_no.asc()" in source
    assert "student.id.asc()" in source
    assert "if first_page:" in source
    assert "select(func.count())" in source
    assert '"nextCursor"' in source
    assert '"filterHash"' in source
    assert '"asOf"' in source

    visibility_pos = source.index("object_visibility")
    class_filter_pos = source.index("student.class_id == normalized_class_id")
    assert visibility_pos < class_filter_pos


def test_t3_my_students_keeps_advisor_role_relation_exclusive():
    source = inspect.getsource(student_svc.list_continuous)
    assert "if is_advisor_scope(scope):" in source
    assert "object_visibility = canonical_visibility" in source
    assert "class_owner_visibility = _class_owner_predicate" in source
    assert "object_visibility = or_(canonical_visibility, class_owner_visibility)" in source
    advisor_pos = source.index("if is_advisor_scope(scope):")
    class_owner_pos = source.index("class_owner_visibility = _class_owner_predicate")
    assert advisor_pos < class_owner_pos


def test_t3_my_students_preserves_direct_counselor_head_teacher_relation_in_sql():
    source = inspect.getsource(student_svc._class_owner_predicate)
    assert "exists(" in source
    assert "SchoolClass.counselor_id == uid" in source
    assert "SchoolClass.head_teacher_id == uid" in source
    assert ".all()" not in source


def _mounted_paths(client: str) -> set[str]:
    # FastAPI 0.141 represents nested APIRouter inclusions with lazy _IncludedRouter entries.
    # The production contract is the final OpenAPI surface, which resolves those inclusions;
    # inspecting app.routes directly would incorrectly see only the framework documentation routes.
    app = FastAPI()
    app.include_router(todos_api.make_router(client), prefix="/api/v1")
    return set(app.openapi().get("paths", {}))


def test_t3_teacher_mobile_students_route_is_additive_and_not_mounted_on_other_clients():
    teacher_paths = _mounted_paths("teacher-mobile")
    admin_paths = _mounted_paths("admin")
    student_paths = _mounted_paths("student-mini")

    assert "/api/v1/teacher-mobile/students" in teacher_paths
    assert "/api/v1/teacher-mobile/todos" in teacher_paths
    assert "/api/v1/teacher-mobile/todos/continuous" in teacher_paths
    assert "/api/v1/admin/students" not in admin_paths
    assert "/api/v1/student-mini/students" not in student_paths
