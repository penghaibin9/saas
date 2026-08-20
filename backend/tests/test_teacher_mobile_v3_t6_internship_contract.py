from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1 import teacher_mobile_internship as route
from app.api.v1 import teacher_mobile_sequential as sequential_route
from app.services import file_business_binding_service
from app.services import file_public_acl_guard
from app.services import teacher_mobile_internship_evidence_service as evidence


def _visit_body(**overrides):
    body = {
        "planId": 101,
        "visitType": "ONSITE",
        "contactPerson": "企业导师",
        "workStatus": "学生在岗状态正常",
        "enterpriseFeedback": "企业反馈学生表现稳定",
        "facts": "本次现场巡访已核对岗位任务、出勤与安全情况。",
        "issues": None,
        "advice": None,
        "needFollow": False,
        "needRisk": False,
        "riskLevel": None,
        "riskReason": None,
        "fileIds": [],
        "location": None,
        "expectedVersion": 7,
    }
    body.update(overrides)
    return body


def test_t6_visit_body_is_strict_versioned_and_location_free():
    parsed = route.VisitEvidenceBody(**_visit_body())
    assert parsed.expectedVersion == 7
    assert parsed.location is None
    with pytest.raises(ValidationError):
        route.VisitEvidenceBody(**_visit_body(location="teacher-gps"))
    with pytest.raises(ValidationError):
        route.VisitEvidenceBody(**_visit_body(fileIds=["1", "2"]))
    with pytest.raises(ValidationError):
        route.VisitEvidenceBody(**{**_visit_body(), "unexpected": True})


def test_t6_routes_keep_canonical_internship_permissions_not_staff_only():
    route_source = inspect.getsource(route)
    sequential_source = inspect.getsource(sequential_route)
    assert 'require_permission("internship.visit.view")' in route_source
    assert 'require_permission("internship.report.review")' in route_source
    assert 'require_permission("internship.visit.manage")' in route_source
    assert 'require_permission("internship.attendance.review")' in sequential_source
    assert "require_staff" not in route_source
    assert "require_staff" not in sequential_source


def test_t6_visit_transaction_locks_record_validates_plan_and_advances_version():
    source = inspect.getsource(evidence.create_visit_evidence)
    assert ".with_for_update()" in source
    assert "current_version != expected" in source
    assert "_validate_plan(db" in source
    assert "_validate_file_ids(user" in source
    assert "InternshipVisit(" in source
    assert "RiskRecord(" in source
    assert "InternshipAuditTrail(" in source
    assert "rec.version = current_version + 1" in source
    assert "db.commit()" in source
    assert '"teacherLocationCaptured": False' in source
    assert "getLocation" not in source


def test_t6_plan_scope_accepts_only_frozen_target_student():
    plan = SimpleNamespace(student_scope="张三，20260002\n李四")
    assert evidence._plan_allows_student(plan, SimpleNamespace(real_name="张三", student_no="20260001"))
    assert evidence._plan_allows_student(plan, SimpleNamespace(real_name="王五", student_no="20260002"))
    assert not evidence._plan_allows_student(plan, SimpleNamespace(real_name="赵六", student_no="20260003"))


def test_t6_file_chain_reuses_existing_internship_visit_binding_and_acl():
    binding_source = inspect.getsource(file_business_binding_service._spec_for)
    acl_source = inspect.getsource(file_public_acl_guard.install)
    evidence_source = inspect.getsource(evidence._validate_file_ids)
    assert '(InternshipVisit, "file_id", "INTERNSHIP_VISIT", "internship_id")' in binding_source
    assert '"INTERNSHIP_VISIT"' in acl_source
    assert '"TEMP_PRIVATE"' in evidence_source
    assert "readyForBusiness" in evidence_source
    assert "bind_file" not in inspect.getsource(evidence.create_visit_evidence)


def test_t6_weekly_reminder_scopes_detail_then_requires_overdue_before_canonical_command():
    source = inspect.getsource(evidence.remind_overdue_weekly_report)
    detail_at = source.index("get_weekly_report_detail")
    overdue_at = source.index('!= "OVERDUE"')
    remind_at = source.index("remind_weekly_report(report_id")
    assert detail_at < overdue_at < remind_at
    assert "DATA_CONFLICT" in source


def test_t6_to_risk_requires_high_and_five_char_reason_before_same_canonical_state_machine():
    body_source = inspect.getsource(sequential_route.AttendanceExceptionHandleBody)
    route_source = inspect.getsource(sequential_route.handle_attendance_exception)
    assert 'Literal["REASONABLE", "ABNORMAL", "TO_RISK"]' in body_source
    assert "min_length=5" in body_source
    assert 'Literal["HIGH"]' in body_source
    assert 'action == "TO_RISK"' in route_source
    assert 'body.riskLevel != "HIGH"' in route_source
    assert "internship_service.handle_attendance_exception" in route_source
    assert "expected_version=body.expectedVersion" in route_source


def test_t6_additive_adapter_does_not_define_new_database_authority():
    source = inspect.getsource(evidence)
    assert "__tablename__" not in source
    assert "declarative_base" not in source
    assert "CREATE TABLE" not in source.upper()
