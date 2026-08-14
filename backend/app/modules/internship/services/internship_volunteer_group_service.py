"""InternshipVolunteerGroup coordination state service.

Enterprise decisions are side facts and never deleted here. A timed-out ACCEPT_INTENT lock is
released lazily to NEEDS_REVISION with an audit trail; students may then revise/resubmit through
the atomic volunteer service.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_audit_service
from app.services.db_service import _as_id

_GROUP_STATUSES = frozenset({"DRAFT", "SUBMITTED", "LOCKED", "NEEDS_REVISION", "APPROVED"})
_DEFAULT_TEACHER_CONFIRM_SLA_HOURS = 48


def _get_group_in_tx(db, *, tenant_id: int, group_id: int, lock: bool = False) -> InternshipVolunteerGroup:
    stmt = select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.id == _as_id(group_id),
        InternshipVolunteerGroup.tenant_id == tenant_id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    group = db.scalar(stmt)
    if not group:
        raise not_found("志愿组不存在或不在当前租户")
    return group


def get_or_create_group_in_tx(db, *, tenant_id: int, record_id: int, student_id: int, batch_id: int, campaign_id: int) -> InternshipVolunteerGroup:
    """Called after InternshipRecord is locked by the canonical A01-10 lock order."""
    group = db.scalar(
        select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.record_id == _as_id(record_id),
            InternshipVolunteerGroup.campaign_id == _as_id(campaign_id),
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).with_for_update()
    )
    if group:
        if group.student_id != _as_id(student_id) or group.batch_id != _as_id(batch_id):
            raise AppException("DATA_CONFLICT", "志愿组与实习记录/批次身份不一致")
        return group
    group = InternshipVolunteerGroup(
        tenant_id=tenant_id,
        record_id=_as_id(record_id),
        student_id=_as_id(student_id),
        batch_id=_as_id(batch_id),
        campaign_id=_as_id(campaign_id),
        status="DRAFT",
        submission_version=0,
    )
    db.add(group)
    db.flush()
    return group


def lazy_release_expired_lock_in_tx(db, *, group: InternshipVolunteerGroup, tenant_id: int, now: datetime | None = None, user=None) -> bool:
    current = now or datetime.utcnow()
    if group.status != "LOCKED":
        return False
    deadline = group.teacher_confirm_deadline
    if deadline is None or deadline > current:
        return False
    before = group.status
    group.status = "NEEDS_REVISION"
    group.last_released_at = current
    group.last_release_reason = "TEACHER_CONFIRM_TIMEOUT"
    group.released_by_user_id = None
    group.revision_requested_at = current
    group.revision_reason = "学校确认期限已过，系统释放企业确认锁，学生可重新修改并提交志愿"
    group.teacher_confirm_deadline = None
    group.version = int(group.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="AUTO_RELEASE_ENTERPRISE_CONFIRM_LOCK",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=before,
        after_status=group.status,
        new_version=group.version,
        reason=group.last_release_reason,
        detail={
            "campaignId": str(group.campaign_id),
            "lockedApplicationId": str(group.locked_application_id or ""),
            "lockedByDecisionId": str(group.locked_by_decision_id or ""),
            "deadlineExpiredAt": current.isoformat(),
        },
    )
    return True


def assert_student_editable_in_tx(db, *, group: InternshipVolunteerGroup, tenant_id: int, now: datetime | None = None) -> None:
    lazy_release_expired_lock_in_tx(db, group=group, tenant_id=tenant_id, now=now)
    if group.status == "LOCKED":
        raise AppException(
            "VOLUNTEER_GROUP_LOCKED",
            "企业已给出拟接收意向，志愿已锁定，需等待学校确认或解除锁定",
            details={"teacherConfirmDeadline": group.teacher_confirm_deadline.isoformat() if group.teacher_confirm_deadline else None},
            http_status=409,
        )
    if group.status == "APPROVED":
        raise AppException("DATA_CONFLICT", "志愿组已由学校批准，不能普通修改")


def mark_submitted_in_tx(db, *, group: InternshipVolunteerGroup, material_snapshot_id: int, submission_version: int, now: datetime | None = None) -> None:
    assert_student_editable_in_tx(db, group=group, tenant_id=group.tenant_id, now=now)
    if int(submission_version) != int(group.submission_version or 0) + 1:
        raise AppException("DATA_CONFLICT", "submissionVersion 必须严格递增")
    group.status = "SUBMITTED"
    group.submission_version = int(submission_version)
    group.current_material_snapshot_id = _as_id(material_snapshot_id)
    group.submitted_at = now or datetime.utcnow()
    group.locked_application_id = None
    group.locked_by_decision_id = None
    group.locked_at = None
    group.teacher_confirm_deadline = None
    group.revision_reason = None
    group.revision_requested_at = None
    group.version = int(group.version or 0) + 1


def lock_for_accept_intent_in_tx(
    db,
    *,
    group: InternshipVolunteerGroup,
    application_id: int,
    decision_id: int,
    teacher_confirm_sla_hours: int | None,
    now: datetime | None = None,
    user=None,
) -> None:
    current = now or datetime.utcnow()
    lazy_release_expired_lock_in_tx(db, group=group, tenant_id=group.tenant_id, now=current, user=user)
    if group.status not in {"SUBMITTED", "LOCKED"}:
        raise AppException("DATA_CONFLICT", f"志愿组状态 {group.status} 不能接受企业拟接收锁")
    if group.status == "LOCKED":
        if group.locked_by_decision_id == _as_id(decision_id) and group.locked_application_id == _as_id(application_id):
            return
        raise AppException("DATA_CONFLICT", "志愿组已被另一条企业拟接收决定锁定")
    hours = int(teacher_confirm_sla_hours or _DEFAULT_TEACHER_CONFIRM_SLA_HOURS)
    if hours < 1 or hours > 168:
        raise AppException("VALIDATION_ERROR", "teacherConfirmSlaHours 必须在 1-168 小时")
    before = group.status
    group.status = "LOCKED"
    group.locked_at = current
    group.locked_application_id = _as_id(application_id)
    group.locked_by_decision_id = _as_id(decision_id)
    group.teacher_confirm_deadline = current + timedelta(hours=hours)
    group.version = int(group.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="LOCK_BY_ENTERPRISE_ACCEPT_INTENT",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=before,
        after_status=group.status,
        new_version=group.version,
        detail={
            "campaignId": str(group.campaign_id),
            "applicationId": str(application_id),
            "decisionId": str(decision_id),
            "teacherConfirmDeadline": group.teacher_confirm_deadline.isoformat(),
        },
    )


def teacher_request_revision_in_tx(db, *, group: InternshipVolunteerGroup, reason: str, user=None, now: datetime | None = None) -> None:
    text = str(reason or "").strip()
    if len(text) < 2:
        raise AppException("VALIDATION_ERROR", "解除/退回志愿锁必须填写原因")
    current = now or datetime.utcnow()
    lazy_release_expired_lock_in_tx(db, group=group, tenant_id=group.tenant_id, now=current, user=user)
    if group.status not in {"LOCKED", "SUBMITTED"}:
        if group.status == "NEEDS_REVISION" and group.revision_reason == text:
            return
        raise AppException("DATA_CONFLICT", f"志愿组状态 {group.status} 不能退回修订")
    before = group.status
    group.status = "NEEDS_REVISION"
    group.revision_requested_at = current
    group.revision_reason = text
    group.last_released_at = current if before == "LOCKED" else group.last_released_at
    group.last_release_reason = "TEACHER_REQUEST_REVISION" if before == "LOCKED" else group.last_release_reason
    group.teacher_confirm_deadline = None
    group.version = int(group.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="REQUEST_VOLUNTEER_REVISION",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=before,
        after_status=group.status,
        new_version=group.version,
        reason=text,
        detail={
            "lockedApplicationId": str(group.locked_application_id or ""),
            "lockedByDecisionId": str(group.locked_by_decision_id or ""),
        },
    )


def teacher_mark_approved_in_tx(db, *, group: InternshipVolunteerGroup, user=None, now: datetime | None = None) -> None:
    current = now or datetime.utcnow()
    lazy_release_expired_lock_in_tx(db, group=group, tenant_id=group.tenant_id, now=current, user=user)
    if group.status not in {"SUBMITTED", "LOCKED"}:
        raise AppException("DATA_CONFLICT", f"志愿组状态 {group.status} 不能批准")
    before = group.status
    group.status = "APPROVED"
    group.approved_at = current
    group.teacher_confirm_deadline = None
    group.version = int(group.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="APPROVE_VOLUNTEER_GROUP",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=before,
        after_status=group.status,
        new_version=group.version,
        detail={
            "lockedApplicationId": str(group.locked_application_id or ""),
            "lockedByDecisionId": str(group.locked_by_decision_id or ""),
        },
    )
