from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.api.v1 import teacher_mobile_students as student_api
from app.core.exceptions import AppException
from app.models import StudentProfile
from app.services import teacher_mobile_student360_projection_service as projection


def test_t4_affairs_summary_does_not_leak_machine_status_values():
    assert projection._affairs_summary(None) == "暂无学工摘要"
    assert projection._affairs_summary(SimpleNamespace(care_level="KEY_CARE", risk_level="HIGH")) == "关怀：重点关怀 · 风险：高"
    assert projection._affairs_summary(SimpleNamespace(care_level="NEW_CODE", risk_level="UNKNOWN")) == "关怀：待确认 · 风险：待确认"


def test_t4_student360_projection_is_sql_scoped_and_read_only_composition():
    source = inspect.getsource(projection)
    assert "compile_teacher_mobile_student_visibility" in source
    assert "StudentProfile.phone" not in source
    assert "phone_encrypted" not in source
    assert "id_card" not in source.lower()
    assert ".limit(10)" in source
    assert "cache_set" not in source
    assert "redis" not in source.lower() or "second Redis version authority" in source
    assert "PsyReferral" not in source
    assert "mental_flag" in source
    assert "CsDiscipline" in source


def test_t4_student360_object_lookup_is_strict_profile_id_not_numeric_student_no_union():
    source = inspect.getsource(projection._student_lookup_condition)
    assert "StudentProfile.id == int(raw)" in source
    assert "StudentProfile.student_no" not in source
    assert "or_(" not in source

    sql = str(projection._student_lookup_condition(StudentProfile, "17").compile(
        compile_kwargs={"literal_binds": True}
    )).lower()
    assert "t_student_profile.id = 17" in sql
    with pytest.raises(AppException):
        projection._student_lookup_condition(StudentProfile, "2026A001")
    with pytest.raises(AppException):
        projection._student_lookup_condition(StudentProfile, "0")


def test_t4_domain_projection_reads_only_active_business_records():
    source = inspect.getsource(projection.get_projection)
    # All four domain master projections have an independent business validity flag in addition
    # to is_deleted. A newer VOID/INACTIVE row must never shadow the latest ACTIVE truth.
    for clause in (
        'AcademicStudent.record_status == "ACTIVE"',
        'GraduationStudent.record_status == "ACTIVE"',
        'EmpStudent.record_status == "ACTIVE"',
        'CsServiceStudent.record_status == "ACTIVE"',
    ):
        assert clause in source


def test_t4_domain_projection_uses_stable_profile_id_before_legacy_student_number():
    source = inspect.getsource(projection.get_projection)
    for model_name in ("AcademicStudent", "GraduationStudent", "EmpStudent", "CsServiceStudent"):
        assert f"_stable_student_domain_link({model_name}, stu)" in source
        assert f"*_stable_student_domain_order({model_name})" in source

    helper = inspect.getsource(projection._stable_student_domain_link)
    assert "model.student_id == student.id" in helper
    assert "model.student_id.is_(None)" in helper
    assert "model.student_no == student.student_no" in helper


def test_t4_projection_and_my_students_share_the_same_mobile_visibility_compiler():
    source = inspect.getsource(projection.get_projection)
    assert "scope = teacher_guard.resolve_teacher_scope(user)" in source
    assert "compile_teacher_mobile_student_visibility(user, student.id, scope=scope)" in source


def test_t4_only_open_workflow_warnings_count_as_active_risk():
    source = inspect.getsource(projection.get_projection)
    assert 'AcademicWarning.record_status == "ACTIVE"' in source
    assert "AcademicWarning.status.in_(_ACTIVE_WARNING_STATUSES)" in source
    assert set(projection._ACTIVE_WARNING_STATUSES) == {"PENDING_HANDLE", "PROCESSING", "ESCALATED"}
    assert "CLOSED" not in projection._ACTIVE_WARNING_STATUSES


def test_t4_student360_actions_are_object_context_not_new_command_authority():
    source = inspect.getsource(projection.get_projection)
    for key in ("RECORD_CONTACT", "NEW_TALK", "FAMILY_CONTACT", "EMPLOYMENT_FOLLOWUP"):
        assert f'"key": "{key}"' in source
    assert '"internshipId"' in source
    assert '"employmentStudentId"' in source
    assert "create_talk" not in source
    assert "create_contact" not in source
    assert "create_referral" not in source
    assert "create_follow" not in source


def test_t4_sensitive_zone_never_projects_psychological_or_discipline_detail():
    source = inspect.getsource(projection.get_projection)
    assert '"detailRestricted": True' in source
    assert '"mental"' in source
    assert '"discipline"' in source
    for forbidden in ("reason_summary", "counselor_note", "doc_no", "discipline.reason"):
        assert forbidden not in source


def test_t4_projection_version_consumes_shared_freshness_when_handoff_exists():
    source = inspect.getsource(projection._projection_version)
    assert "mobile_freshness_service" in source
    assert "projection_version" in source
    assert 'scoped["studentId"]' in source
    assert "increment_with_ttl" not in source
    assert "cache_set" not in source


def test_t4_student360_route_is_additive_under_teacher_mobile_students_router():
    paths = {route.path for route in student_api.router.routes if getattr(route, "path", None)}
    assert "/students" in paths
    assert "/students/{student_id}/projection" in paths


def test_t4_risk_rollup_prefers_high_then_medium_then_low():
    assert projection._risk_level(warning_count=0, internship_risk="LOW", affairs_risk="LOW") == "LOW"
    assert projection._risk_level(warning_count=1, internship_risk="LOW", affairs_risk="LOW") == "MEDIUM"
    assert projection._risk_level(warning_count=0, internship_risk="HIGH", affairs_risk="LOW") == "HIGH"
