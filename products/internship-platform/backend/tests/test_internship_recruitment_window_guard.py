from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.core.exceptions import AppException
from app.modules.internship.services import internship_recruitment_window_guard as guard


def _campaign(now: datetime):
    return SimpleNamespace(
        status="OPEN",
        invite_start_at=now - timedelta(hours=1),
        invite_end_at=now + timedelta(hours=1),
        position_submit_start_at=now - timedelta(hours=1),
        position_submit_end_at=now + timedelta(hours=1),
        student_select_start_at=now - timedelta(hours=1),
        student_select_end_at=now + timedelta(hours=1),
        enterprise_decision_start_at=now - timedelta(hours=1),
        enterprise_decision_end_at=now + timedelta(hours=1),
        school_confirm_start_at=now - timedelta(hours=1),
        school_confirm_end_at=now + timedelta(hours=1),
    )


def test_shared_guard_covers_all_five_campaign_operation_windows():
    now = datetime(2026, 9, 10, 8, 0, 0)
    campaign = _campaign(now)
    for operation in ("INVITE", "POSITION_SUBMIT", "STUDENT_SELECT", "ENTERPRISE_DECISION", "SCHOOL_CONFIRM"):
        assert guard.assert_campaign_operation_window(campaign, operation, now=now) == now


def test_shared_guard_is_fail_closed_for_status_missing_window_and_outside_window():
    now = datetime(2026, 9, 10, 8, 0, 0)
    campaign = _campaign(now)
    campaign.status = "FROZEN"
    try:
        guard.assert_campaign_operation_window(campaign, "STUDENT_SELECT", now=now)
    except AppException as exc:
        assert exc.code == "DATA_CONFLICT"
    else:
        raise AssertionError("FROZEN campaign must reject normal window writes")

    campaign = _campaign(now)
    campaign.invite_end_at = None
    try:
        guard.assert_campaign_operation_window(campaign, "INVITE", now=now)
    except AppException as exc:
        assert exc.code == "DATA_CONFLICT"
    else:
        raise AssertionError("half configured invite window must fail closed")

    campaign = _campaign(now)
    campaign.school_confirm_start_at = now + timedelta(minutes=1)
    campaign.school_confirm_end_at = now + timedelta(hours=1)
    try:
        guard.assert_campaign_operation_window(campaign, "SCHOOL_CONFIRM", now=now)
    except AppException as exc:
        assert exc.code == "DATA_CONFLICT"
    else:
        raise AssertionError("operation before its window must fail closed")


def test_unregistered_window_operation_is_programmer_error():
    try:
        guard.assert_campaign_operation_window(_campaign(datetime.utcnow()), "NOT_REAL")
    except RuntimeError as exc:
        assert "unregistered recruitment campaign operation window" in str(exc)
    else:
        raise AssertionError("unknown operation must never silently pass")
