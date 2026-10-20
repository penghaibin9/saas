"""学工四端 UI 与审批证据静态合同。

只检查本轮修复的代码合同，不启动教务、实习、毕设等无关业务。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dorm_transfer_projection_exposes_human_readable_approval_evidence():
    source = _read("backend/app/services/affairs_dorm_projection_service.py")
    for field in (
        '"fromBuildingName"', '"fromRoomNo"', '"fromBedNo"', '"fromBedLabel"',
        '"toBuildingName"', '"toRoomNo"', '"toBedNo"', '"toBedLabel"',
        '"allowedActions"',
    ):
        assert field in source
    assert 'node = str(item.get("currentNode") or item.get("status") or "")' in source
    assert 'if node == "COUNSELOR_REVIEW" and context.scope_type == "CLASS":' in source
    assert 'elif node == "DORM_MANAGER_REVIEW" and context.scope_type == "DORM_BUILDING":' in source
    assert 'can_review = assigned_to_current' in source
    assert '"allowedActions": ["APPROVE", "REJECT"] if can_review else []' in source


def test_pc_and_mobile_dorm_approval_require_source_target_and_version():
    pc = _read("frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue")
    mobile = _read("miniapp/src/pages/teacher/dorm-review/index.vue")
    for source in (pc, mobile):
        assert "fromBedLabel" in source
        assert "toBedLabel" in source
        assert "allowedActions" in source
        assert "version" in source
    assert ':disabled="!row.fromBedLabel || !row.toBedLabel || !hasVersion(row)"' in pc
    assert "核对后通过" in pc
    assert "床位信息不完整" in mobile


def test_funding_publicity_manual_confirm_keeps_optimistic_lock_version():
    pc = _read("frontend/src/modules/studentAffairs/views/funding/FundingPublicityView.vue")
    api = _read("frontend/src/modules/studentAffairs/api/studentAffairs.api.js")
    backend = _read("backend/app/api/v1/student_affairs.py")
    service = _read("backend/app/services/affairs_funding_service.py")
    assert "confirmFundingPublicity(row.applicationId, row.version)" in pc
    assert "confirmFundingPublicity(id, version)" in api
    assert "class FundingVersionOnlyBody(BaseModel):" in backend
    assert 'version: int = Field(..., description="乐观锁版本（必填）")' in backend
    assert '"currentNode": x.status if x.status in FUND_NODES else "", "version": x.version' in service


def test_credit_appeal_contract_matches_backend_numeric_rules():
    backend = _read("backend/app/services/affairs_activity_service.py")
    portal = _read("student-portal/src/views/affairs/AffairsFourEndView.vue")
    mini = _read("miniapp/src/pages/student/affairs/activity.vue")
    pc = _read("frontend/src/modules/studentAffairs/views/activity/CreditAppealView.vue")
    assert "9999.99" in backend
    for source in (portal, mini, pc):
        assert "9999.99" in source
        assert "最多保留2位小数" in source
        assert "主张数值（选填）" not in source


def test_teacher_dangerous_actions_have_nonempty_evidence_guards():
    mental = _read("miniapp/src/pages/teacher/affairs/mental/index.vue")
    mental_pc = _read("frontend/src/modules/studentAffairs/views/mental/MentalCrisisView.vue")
    talk = _read("miniapp/src/pages/teacher/affairs/talk/index.vue")
    leave = _read("miniapp/src/pages/teacher/affairs-leave/index.vue")
    review = _read("miniapp/src/pages/teacher/affairs-review/index.vue")
    assert "确认升级为危机" in mental
    assert "确认关闭心理关注" in mental
    assert "升级依据（5-300字）" in mental_pc
    assert "message=\"升级后将生成正式风险中枢记录" in mental_pc
    assert "升级说明（可空）" not in mental_pc
    assert "处理说明需5-300字" in talk
    assert "实际返校时间不能晚于当前时间" in leave
    assert "确认关闭风险" in review
    assert "adjustment.targetLevel" in review
    assert "确认困难等级调整" in review
    assert "this.visibleVersion(row, detail)" in review


def test_mental_allowed_actions_are_centralized_and_match_backend_transitions():
    service = _read("backend/app/services/affairs_mental_service.py")
    pc = _read("frontend/src/modules/studentAffairs/views/mental/MentalReferralFollowView.vue")
    assert '"allowedActions": _allowed_actions(x)' in service
    assert 'if x.status == "ESCALATED"' in service
    assert 'return ["CLOSE"]' in service
    assert 'if "FOLLOW" not in _allowed_actions(x)' in service
    assert 'if "ESCALATE" not in _allowed_actions(x)' in service
    assert "危机升级依据需5-300字" in service
    assert ':pagination="pagination"' in pc
    assert 'Array.isArray(row.allowedActions)' in pc
    assert "Array.isArray(row.allowedActions) ? row.allowedActions : []" in pc
    assert "ESCALATED: ['CLOSE']" not in pc


def test_date_only_leave_range_is_inclusive_and_same_day_is_valid():
    from app.core.exceptions import AppException
    from app.services.affairs_leave_date_contract import normalize_range

    start, end = normalize_range("2026-08-01", "2026-08-01")
    assert start == datetime(2026, 7, 31, 16, 0, 0)
    assert end == datetime(2026, 8, 1, 15, 59, 59)
    assert end > start

    with pytest.raises(AppException):
        normalize_range("2026-08-02", "2026-08-01")
    with pytest.raises(AppException):
        normalize_range("not-a-date", "2026-08-01")


def test_all_leave_entrypoints_install_the_same_date_contract():
    date_contract = _read("backend/app/services/affairs_leave_date_contract.py")
    four_end = _read("backend/app/api/v1/affairs_four_end.py")
    assert "service.apply_leave = wrapped" in date_contract
    assert "install_leave_date_contract()" in four_end
    assert "normalize_range(" in four_end
    assert "normalize_reason(" in four_end
    assert 'pattern=r"^\\d{6}$"' in four_end


def test_mobile_teacher_adapters_preserve_authority_pagination_and_versions():
    """移动端不得在适配层截断待办或丢失服务层的乐观锁版本。"""
    impl = _read("backend/app/services/_mobile_teacher_service_impl.py")
    routes = _read("backend/app/api/v1/mobile.py")

    assert 'def affairs_aid_pending(user: dict, page: int = 1, page_size: int = 20,' in impl
    assert 'pending_kind=kind, keyword=keyword' in impl
    assert 'def affairs_funding_pending(user: dict, page: int = 1, page_size: int = 20,' in impl
    assert 'pending_only=True, keyword=keyword' in impl
    assert 'def affairs_funding_review(user: dict, app_id: str, action: str, reason: str = "",' in impl
    assert 'expected_version=expected_version' in impl

    for command in (
        'leave_svc.confirm_cancel', 'leave_svc.proxy_cancel', 'leave_svc.handle_overdue',
        'leave_svc.approve_extension', 'svc.review_remove', 'dorm.review_transfer',
        'dorm.handle_exception', 'talk.follow_up', 'mental.follow_referral',
        'mental.escalate_crisis', 'mental.close_referral',
    ):
        start = impl.index(command)
        assert 'expected_version=' in impl[start:start + 280], command

    for marker in (
        'body.get("actualReturnAt"), body.get("reason"), body.get("note"), body.get("version")',
        'body.get("actualReturnAt") or "", body.get("note"), body.get("version")',
        'expected_version=(body or {}).get("version")',
        'body.get("note") or "", body.get("version")',
    ):
        assert marker in routes


def test_student_service_work_order_has_a_real_teacher_mobile_queue_and_result_readback():
    routes = _read("backend/app/api/v1/mobile.py")
    teacher_api = _read("miniapp/src/services/teacherApi.js")
    teacher_page = _read("miniapp/src/pages/teacher/campus-service/index.vue")
    student_service = _read("backend/app/services/mobile_student_service.py")

    assert 'require_permission("campusService.workOrder.view")' in routes
    assert 'require_permission("campusService.workOrder.handle")' in routes
    assert 'campus_service.list_work_orders(page, pageSize' in routes
    assert 'campus_service.handle_work_order(' in routes
    assert 'campus_service.close_work_order(' in routes
    assert 'getCampusWorkOrders' in teacher_api
    assert 'handleCampusWorkOrder' in teacher_api
    assert '服务工单' in teacher_page
    assert 'version: order.version' in teacher_page
    assert '工单已办结，学生可查看处理结果' in teacher_page
    assert '"COMPLETED": "已办结"' in student_service
    campus_service = _read("backend/app/services/campus_service_service.py")
    outbox = _read("backend/app/services/message_event_outbox_service.py")
    assert 'event_code="CAMPUS_SERVICE.WORKORDER_UPDATED"' in campus_service
    assert '_drain_work_order_notice(outbox_id)' in campus_service
    assert '"CAMPUS_SERVICE.WORKORDER_UPDATED"' in outbox
    registry = _read("backend/app/services/message_action_registry.py")
    focus = _read("backend/app/services/mobile_focus_contract.py")
    assert '"student.campus-service.work-order"' in registry
    assert '"/pages/student/my-work/index": "caseId"' in focus
