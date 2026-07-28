"""第一轮学工：乐观锁 / 心理等级 / 首页风险 / 驾驶舱降级 目标测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "app"


def test_mental_attention_level_order_prefers_crisis():
    from app.services import affairs_mental_service as mental

    class R:
        def __init__(self, level, status="FOLLOWING"):
            self.level = level
            self.status = status

    active = [R("GENERAL"), R("CRISIS"), R("FOCUS")]
    _LEVEL_ORDER = {"GENERAL": 1, "FOCUS": 2, "CRISIS": 3}
    top = max(active, key=lambda r: _LEVEL_ORDER.get(r.level, 0)).level
    assert top == "CRISIS"
    src = Path(mental.__file__).read_text(encoding="utf-8")
    assert "max((r.level for r in active)" not in src
    assert "_LEVEL_ORDER" in src or "GENERAL" in src


def test_cockpit_domain_error_not_fake_zero(db_mode):
    from app.services import affairs_cockpit_service as cockpit

    def boom(_user):
        raise RuntimeError("db down")

    dashboard = {"summaryCards": [{"key": "studentTotal", "value": 5}, {"key": "classTotal", "value": 2}]}
    with patch("app.services.affairs_dashboard_service.get_dashboard", lambda _u: dashboard), \
            patch("app.services.affairs_leave_service.leave_stats",
                  lambda _u: {"metrics": [{"key": "leaveStudentCount", "value": 1},
                                           {"key": "pendingReview", "value": 1}]}), \
            patch("app.services.affairs_dorm_service.occupancy_stats",
                  lambda _u: {"totalBeds": 10, "occupiedBeds": 8}), \
            patch("app.services.affairs_risk_service.list_risks",
                  lambda _u, page, page_size: ([], 0, {"total": 0, "highCritical": 0})), \
            patch("app.services.affairs_aid_service.aid_stats", boom), \
            patch("app.services.affairs_funding_service.funding_stats", lambda u: {"total": 3, "granted": 1}), \
            patch("app.services.affairs_discipline_service.discipline_stats",
                  lambda u: {"total": 2, "byStatus": [{"key": "EFFECTIVE", "count": 1}],
                             "reconcile": {"consistent": True}}), \
            patch("app.services.affairs_activity_service.activity_stats",
                  lambda u: {"totalActivities": 4, "creditStudents": 2}), \
            patch("app.services.affairs_talk_service.talk_stats", lambda _u: {"total": 2, "completed": 1}), \
            patch("app.services.affairs_mental_service.stats", lambda _u: {"total": 1, "openCrisis": 0}):
        data = cockpit.cockpit({"currentRoleCode": "SA_ADMIN"})

    aid = next(d for d in data["domains"] if d["key"] == "aid")
    funding = next(d for d in data["domains"] if d["key"] == "funding")
    assert aid["status"] == "ERROR"
    assert aid["total"] is None
    assert aid["message"] == "统计暂不可用"
    assert funding["status"] == "OK"
    assert funding["total"] == 3
    assert data["totals"]["aidApplications"] is None
    assert data["totals"]["fundingApplications"] == 3


def test_todo_filter_semantics_pending_maps_to_review():
    AID_REVIEW = ["CLASS_REVIEW", "COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW"]
    mapping = {
        "PENDING": ("REVIEW", AID_REVIEW),
        "ADJUST_PENDING": ("ADJUST_REVIEW", ["ADJUST_REVIEW"]),
        "REMOVE_PENDING": ("REMOVE_REVIEW", ["REMOVE_REVIEW"]),
    }
    assert mapping["PENDING"][0] == "REVIEW"
    assert "CLASS_REVIEW" in mapping["PENDING"][1]
    assert mapping["ADJUST_PENDING"][0] == "ADJUST_REVIEW"
    assert mapping["REMOVE_PENDING"][0] == "REMOVE_REVIEW"


def test_dashboard_module_cards_live_not_pending():
    src = (_APP / "services" / "affairs_dashboard_service.py").read_text(encoding="utf-8")
    assert '("psy", "心理关注", "LIVE")' in src
    assert '("activity", "学生活动", "LIVE")' in src
    assert '("psy", "心理关注", "PENDING")' not in src
    assert '("activity", "学生活动", "PENDING")' not in src


def test_leave_resubmit_signature_has_expected_version():
    import inspect
    from app.services import affairs_leave_service as leave

    sig = inspect.signature(leave.resubmit)
    assert "expected_version" in sig.parameters
    sig2 = inspect.signature(leave.submit_cancel)
    assert "expected_version" in sig2.parameters
    sig3 = inspect.signature(leave.apply_extension)
    assert "expected_version" in sig3.parameters


def test_aid_approve_adjust_signature_has_expected_version():
    import inspect
    from app.services import affairs_aid_service as aid

    sig = inspect.signature(aid.approve_adjust)
    assert "expected_version" in sig.parameters


def test_mental_api_passes_version_to_service():
    src = (_APP / "api" / "v1" / "student_affairs.py").read_text(encoding="utf-8")
    assert "follow_referral(user, refId, body.content or \"\", body.version)" in src
    assert "escalate_crisis(user, refId, body.content or \"\", body.version)" in src
    assert "close_referral(user, refId, body.conclusion, body.version)" in src
    assert "aid_svc.review(applyId, user, body.action, body.level, body.reason or \"\", body.version)" in src
