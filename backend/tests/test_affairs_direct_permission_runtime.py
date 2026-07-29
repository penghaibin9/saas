"""教师学工端点自身校验与统一运行时预检必须使用同一PC权限码。"""
from __future__ import annotations


def test_direct_activity_and_appeal_routes_do_not_inherit_dashboard_permission():
    from app.services import affairs_four_end_contract as contract

    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs/activities/ongoing", "GET",
    ) == ("studentAffairs.activity.publish",)
    assert contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs/activities/123/checkin-token", "GET",
    ) == ("studentAffairs.activity.publish",)

    appeal_codes = contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs/appeals/AID_OBJECTION", "GET",
    )
    assert "studentAffairs.dashboard.view" not in appeal_codes
    assert "studentAffairs.aid.approve" in appeal_codes
    assert "studentAffairs.funding.publicity.manage" in appeal_codes
    assert "studentAffairs.discipline.appeal.review" in appeal_codes
    assert "studentAffairs.activity.confirm" in appeal_codes


def test_student_candidate_runtime_precheck_uses_business_permissions():
    from app.services import affairs_four_end_contract as contract

    codes = contract._teacher_permissions(
        "/api/v1/mobile/teacher/affairs/student-candidates", "GET",
    )
    assert "studentAffairs.dashboard.view" not in codes
    assert codes == (
        "studentAffairs.talk.create",
        "studentAffairs.mental.manage",
        "studentAffairs.risk.psyDetail.view",
    )
