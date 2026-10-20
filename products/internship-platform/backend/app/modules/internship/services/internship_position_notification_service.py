"""Durable in-app notices for school decisions on enterprise-supplied positions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.internship_enterprise_portal import (
    InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember,
)
from app.services.message_action_registry import validate_action
from app.services.message_event_outbox_service import emit_message_event


_RECIPIENT_ROLES = ("COMPANY_ADMIN", "HR")


def _recipient_refs(db, *, tenant_id: int, company_id: int, campaign_id: int) -> list[dict]:
    now = datetime.utcnow()
    user_ids = db.scalars(
        select(InternshipEnterpriseMember.user_id)
        .join(
            InternshipEnterpriseAccessGrant,
            InternshipEnterpriseAccessGrant.member_id == InternshipEnterpriseMember.id,
        )
        .where(
            InternshipEnterpriseMember.tenant_id == tenant_id,
            InternshipEnterpriseMember.company_id == company_id,
            InternshipEnterpriseMember.status == "ACTIVE",
            InternshipEnterpriseMember.member_role.in_(_RECIPIENT_ROLES),
            InternshipEnterpriseMember.is_deleted.is_(False),
            InternshipEnterpriseAccessGrant.tenant_id == tenant_id,
            InternshipEnterpriseAccessGrant.company_id == company_id,
            InternshipEnterpriseAccessGrant.campaign_id == campaign_id,
            InternshipEnterpriseAccessGrant.grant_type == "RECRUITMENT",
            InternshipEnterpriseAccessGrant.status == "ACTIVE",
            InternshipEnterpriseAccessGrant.valid_from <= now,
            InternshipEnterpriseAccessGrant.valid_until >= now,
            InternshipEnterpriseAccessGrant.is_deleted.is_(False),
        )
        .distinct()
        .order_by(InternshipEnterpriseMember.user_id.asc())
    ).all()
    return [{"userId": int(user_id), "receiverType": "ENTERPRISE"} for user_id in user_ids]


def emit_school_position_notice_in_tx(db, *, position, action: str, reason: str = ""):
    """Write one event in the school's status transaction; return None when no portal recipient exists."""
    campaign_id = int(position.campaign_id or 0)
    if campaign_id <= 0:
        return None
    recipients = _recipient_refs(
        db,
        tenant_id=int(position.tenant_id),
        company_id=int(position.company_id),
        campaign_id=campaign_id,
    )
    if not recipients:
        return None

    normalized = str(action or "").strip().upper()
    title = "岗位状态已调整"
    content = f"岗位“{position.title}”的学校审核状态已更新，请进入岗位详情核对。"
    event_code = "INTERNSHIP.POSITION.STATUS_CHANGED"
    if normalized == "RETURN":
        event_code = "INTERNSHIP.POSITION.RETURNED"
        title = f"{position.title} · 待补正"
        content = f"学校退回了岗位“{position.title}”。补正意见：{str(reason or '').strip()}"
    elif normalized == "PUBLISH":
        event_code = "INTERNSHIP.POSITION.PUBLISHED"
        title = f"{position.title} · 已上架"
        content = f"岗位“{position.title}”已通过学校审核并进入当前招聘季的学生岗位目录。"
    elif normalized == "OFFLINE":
        title = f"{position.title} · 已下架"
        content = f"岗位“{position.title}”已由学校下架，学生端不再展示。请进入详情核对后续安排。"
    elif normalized == "SUSPEND":
        title = f"{position.title} · 已暂停"
        content = f"岗位“{position.title}”已暂停招聘，请进入详情核对状态和后续安排。"
    elif normalized == "ARCHIVE":
        title = f"{position.title} · 已归档"
        content = f"岗位“{position.title}”已归档，可继续查阅历史资料。"
    else:
        return None

    action_key, action_params = validate_action(
        "enterprise.internship.position",
        {"positionId": str(position.id), "campaignId": str(campaign_id)},
    )
    return emit_message_event(
        db,
        event_code=event_code,
        source_module="internship",
        source_biz_type="INTERNSHIP_POSITION",
        source_biz_id=int(position.id),
        recipient_refs=recipients,
        title=title,
        content=content,
        action_key=action_key,
        action_params=action_params,
        dedup_key=f"{event_code}:POSITION:{int(position.id)}:v{int(position.version or 0)}",
    )
