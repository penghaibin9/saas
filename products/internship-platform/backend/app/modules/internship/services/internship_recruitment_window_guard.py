"""Shared fail-closed RecruitmentCampaign operation-window contract.

Campaign.status + canonical time fields are the only phase truth. Services must not copy window
semantics or persist a second phase column. A02/A03 may reuse the same guard for POSITION_SUBMIT
and student catalog/submit paths.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException

_WINDOW_FIELDS = {
    "INVITE": ("invite_start_at", "invite_end_at", "企业邀请"),
    "POSITION_SUBMIT": ("position_submit_start_at", "position_submit_end_at", "岗位提交"),
    "STUDENT_SELECT": ("student_select_start_at", "student_select_end_at", "学生选岗"),
    "ENTERPRISE_DECISION": ("enterprise_decision_start_at", "enterprise_decision_end_at", "企业处理"),
    "SCHOOL_CONFIRM": ("school_confirm_start_at", "school_confirm_end_at", "学校确认"),
}


def assert_campaign_operation_window(
    campaign,
    operation: str,
    *,
    now: datetime | None = None,
    allowed_statuses: frozenset[str] = frozenset({"OPEN"}),
) -> datetime:
    op = str(operation or "").upper()
    config = _WINDOW_FIELDS.get(op)
    if config is None:
        raise RuntimeError(f"unregistered recruitment campaign operation window: {op}")
    status = str(campaign.status or "").upper()
    if status not in allowed_statuses:
        raise AppException("DATA_CONFLICT", f"招聘季状态 {status or '-'} 不允许执行{config[2]}")
    start_field, end_field, label = config
    start = getattr(campaign, start_field, None)
    end = getattr(campaign, end_field, None)
    if start is None or end is None:
        raise AppException("DATA_CONFLICT", f"招聘季未配置完整{label}时间窗")
    current = now or datetime.utcnow()
    if current < start or current > end:
        raise AppException("DATA_CONFLICT", f"当前不在{label}时间窗内")
    return current
