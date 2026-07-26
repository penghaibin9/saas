"""学工四端 UI 与审批证据静态合同。

只检查本轮修复的代码合同，不启动教务、实习、毕设等无关业务。
"""
from __future__ import annotations

from pathlib import Path


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
    assert 'if item.get("status") in dorm.TRANSFER_NODES' in source


def test_pc_and_mobile_dorm_approval_require_source_target_and_version():
    pc = _read("frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue")
    mobile = _read("miniapp/src/pages/teacher/dorm-review/index.vue")
    for source in (pc, mobile):
        assert "fromBedLabel" in source
        assert "toBedLabel" in source
        assert "allowedActions" in source
        assert "version" in source
    assert "审批人必须核对原床、目标床" in pc
    assert "核对后通过" in pc
    assert "床位信息不完整" in mobile


def test_credit_appeal_contract_matches_backend_numeric_rules():
    backend = _read("backend/app/services/affairs_credit_appeal_reliability.py")
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
    assert "选择等级并通过" in review


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
    assert "ESCALATED: ['CLOSE']" in pc
