"""PR #101 production audit: fail-closed scope, bounded pages and safe XLSX reads."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.routers import course_selection_router
from app.modules.academic_affairs.routers import grade_core_router
from app.modules.academic_affairs.routers import scheduling_operations_router
from app.modules.academic_affairs.services import academic_affairs_production_audit_guard as guard
from app.modules.academic_affairs.services import academic_affairs_selection_read_service as selection_read


def test_only_tenant_all_is_unscoped_and_teacher_is_own_course_scope():
    tenant_all = SimpleNamespace(scope_type="TENANT_ALL", role_codes={"ACADEMIC_ADMIN"})
    assert guard._selection_scope_values(None, tenant_all) is None

    teacher = SimpleNamespace(
        scope_type="NONE",
        role_codes={"ACADEMIC_TEACHER"},
        user_id="u_teacher01",
        login_name="teacher01",
    )
    class_ids, college_ids, teacher_keys = guard._selection_scope_values(None, teacher)
    assert not class_ids and not college_ids
    assert "teacher01" in teacher_keys

    unknown = SimpleNamespace(scope_type="NONE", role_codes=set(), user_id="", login_name="")
    with pytest.raises(AppException) as exc:
        guard._selection_scope_values(None, unknown)
    assert exc.value.code == "NO_DATA_SCOPE"


def test_selection_scope_guard_is_installed_on_existing_owner_at_package_import():
    assert selection_read._production_audit_guard_installed is True
    assert selection_read._scope_values is guard._selection_scope_values
    assert selection_read._scope_course_query is guard._selection_scope_course_query
    assert selection_read.get_conflict_report is guard._selection_conflict_report
    assert course_selection_router.selection_svc.get_conflict_report is guard._selection_conflict_report


def test_page_size_guard_rejects_oversized_requests():
    assert guard._bounded_page_size(1, default=20) == 1
    assert guard._bounded_page_size(200, default=20) == 200
    for value in (0, -1, 201, 100000):
        with pytest.raises(AppException) as exc:
            guard._bounded_page_size(value, default=20)
        assert exc.value.code == "VALIDATION_ERROR"


def test_conflict_detail_redacts_student_identity_and_like_wildcards_are_literal():
    detail = "studentNo=20240001 studentName=张三 courseName=高等数学 reason=上课时间冲突"
    redacted = guard._redact_conflict_detail(detail)
    assert "20240001" not in redacted
    assert "张三" not in redacted
    assert "courseName=高等数学" in redacted
    assert guard._escape_like(r"20%24_01\\x") == r"20\%24\_01\\\\x"


def test_conflict_route_keeps_d6_owner_and_adds_bounded_pagination():
    source = inspect.getsource(course_selection_router.sel_conflict_report)
    assert "pageSize: int = Query(50, ge=1, le=200)" in source
    assert "selection_svc.get_conflict_report(user, batchId, studentNo, page, pageSize)" in source
    assert course_selection_router.sel_conflict_report.__module__.endswith("course_selection_router")


def test_xlsx_routes_keep_existing_owners_and_use_shared_safe_upload_guard():
    schedule_source = inspect.getsource(scheduling_operations_router.schedule_import_xlsx)
    grade_source = inspect.getsource(grade_core_router.grade_import_xlsx)
    for source in (schedule_source, grade_source):
        assert "read_safe_upload" in source
        assert "file.read(" not in source
    assert "sched_svc.import_items" in schedule_source
    assert "grade_svc.grade_import_dry_run" in grade_source
    assert scheduling_operations_router.schedule_import_xlsx.__module__.endswith("scheduling_operations_router")
    assert grade_core_router.grade_import_xlsx.__module__.endswith("grade_core_router")
