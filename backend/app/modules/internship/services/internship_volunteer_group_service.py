"""InternshipVolunteerGroup coordination state service.

Enterprise decisions are side facts and never deleted here. A timed-out ACCEPT_INTENT lock is
released lazily to NEEDS_REVISION and the linked decision is expired in the same transaction.
Student unlock requests remain requests only; school release is the authority that supersedes an
active enterprise intent and restores editability.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_audit_service
from app.services.db_service import _as_id, _tid, session

_GROUP_STATUSES = frozenset({"DRAFT", "SUBMITTED", "LOCKED", "NEEDS_REVISION", "APPROVED", "CLOSED"})
_DEFAULT_TEACHER_CONFIRM_SLA_HOURS = 48


def _actor_user_id(user) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else None


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


def _locked_decision_in_tx(db, group: InternshipVolunteerGroup, *, lock: bool = True):
    if not group.locked_by_decision_id:
        return None
    from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision

    stmt = select(InternshipEnterpriseApplicationDecision).where(
        InternshipEnterpriseApplicationDecision.id == group.locked_by_decision_id,
        InternshipEnterpriseApplicationDecision.tenant_id == group.tenant_id,
        InternshipEnterpriseApplicationDecision.volunteer_group_id == group.id,
        InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _set_effect(decision, *, effect_status: str, reason: str) -> bool:
    if not decision or decision.effect_status == effect_status:
        return False
    if decision.effect_status == "CONSUMED":
        raise AppException("DATA_CONFLICT", "已消费的企业拟接收决定不能被释放或失效")
    decision.effect_status = effect_status
    decision.superseded_reason = reason
    decision.version = int(decision.version or 0) + 1
    return True


def _message_in_tx(db, *, tenant_id: int, receiver_user_id: int | None, title: str, content: str,
                   source_biz_id: int | None, action_key: str, action_params: dict) -> None:
    if not receiver_user_id:
        return
    from app.models import UnifiedMessage

    db.add(UnifiedMessage(
        tenant_id=tenant_id,
        receiver_id=int(receiver_user_id),
        receiver_user_id=int(receiver_user_id),
        receiver_context_key="GLOBAL",
        source_module="internship",
        source_biz_id=source_biz_id,
        title=title[:500],
        content=content[:2000],
        message_type="TODO_NOTICE",
        category="TODO",
        priority="IMPORTANT",
        status="UNREAD",
        require_ack=False,
        delivery_status="PENDING",
        action_key=action_key,
        action_params_json=action_params,
    ))


def _student_user_id_in_tx(db, group: InternshipVolunteerGroup) -> int | None:
    from app.models import StudentAccountLink

    return db.scalar(select(StudentAccountLink.user_id).where(
        StudentAccountLink.tenant_id == group.tenant_id,
        StudentAccountLink.student_id == group.student_id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    ))


def _advisor_user_id_in_tx(db, group: InternshipVolunteerGroup) -> int | None:
    from app.models import InternshipRecord

    return db.scalar(select(InternshipRecord.advisor_user_id).where(
        InternshipRecord.id == group.record_id,
        InternshipRecord.tenant_id == group.tenant_id,
        InternshipRecord.is_deleted.is_(False),
    ))


def _notify_lock_in_tx(db, *, group: InternshipVolunteerGroup, decision_id: int) -> None:
    params = {
        "campaignId": str(group.campaign_id),
        "volunteerGroupId": str(group.id),
        "applicationId": str(group.locked_application_id or ""),
        "teacherConfirmDeadline": group.teacher_confirm_deadline.isoformat() if group.teacher_confirm_deadline else None,
    }
    _message_in_tx(
        db, tenant_id=group.tenant_id, receiver_user_id=_student_user_id_in_tx(db, group),
        title="企业已拟接收，等待学校确认",
        content="你的志愿已进入学校确认阶段，确认前不能直接修改；如需调整可提交改志愿申请。",
        source_biz_id=decision_id, action_key="INTERNSHIP_ENTERPRISE_ACCEPT_INTENT", action_params=params,
    )
    _message_in_tx(
        db, tenant_id=group.tenant_id, receiver_user_id=_advisor_user_id_in_tx(db, group),
        title="存在企业拟接收待确认",
        content="学生志愿已被企业拟接收锁定，请在学校确认期限内完成审核或解除锁。",
        source_biz_id=decision_id, action_key="INTERNSHIP_TEACHER_CONFIRM_ACCEPT_INTENT", action_params=params,
    )


def lazy_release_expired_lock_in_tx(db, *, group: InternshipVolunteerGroup, tenant_id: int, now: datetime | None = None, user=None) -> bool:
    current = now or datetime.utcnow()
    if group.status != "LOCKED":
        return False
    deadline = group.teacher_confirm_deadline
    if deadline is None or deadline > current:
        return False

    decision = _locked_decision_in_tx(db, group, lock=True)
    if decision and decision.decision_status == "ACCEPT_INTENT" and decision.effect_status == "ACTIVE":
        _set_effect(decision, effect_status="EXPIRED", reason="TEACHER_CONFIRM_TIMEOUT")

    before = group.status
    group.status = "NEEDS_REVISION"
    group.released_at = current
    group.release_reason = "TEACHER_CONFIRM_TIMEOUT"
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
        reason=group.release_reason,
        detail={
            "campaignId": str(group.campaign_id),
            "lockedApplicationId": str(group.locked_application_id or ""),
            "lockedByDecisionId": str(group.locked_by_decision_id or ""),
            "deadlineExpiredAt": current.isoformat(),
            "decisionEffect": decision.effect_status if decision else None,
        },
    )
    params = {"campaignId": str(group.campaign_id), "volunteerGroupId": str(group.id)}
    _message_in_tx(
        db, tenant_id=group.tenant_id, receiver_user_id=_student_user_id_in_tx(db, group),
        title="学校确认超时，志愿已恢复可编辑",
        content="本次企业拟接收已失效，你可以调整志愿并重新提交。",
        source_biz_id=group.locked_by_decision_id, action_key="INTERNSHIP_ACCEPT_INTENT_EXPIRED", action_params=params,
    )
    _message_in_tx(
        db, tenant_id=group.tenant_id,
        receiver_user_id=(decision.decided_by_user_id if decision else None),
        title="学校确认超时，拟接收已释放",
        content="学校未在确认期限内完成落岗，本次拟接收已失效。",
        source_biz_id=group.locked_by_decision_id, action_key="INTERNSHIP_ACCEPT_INTENT_EXPIRED", action_params=params,
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
    if group.status in {"APPROVED", "CLOSED"}:
        raise AppException("DATA_CONFLICT", "志愿组已由学校确认，不能普通修改")


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
    group.unlock_requested_at = None
    group.unlock_request_reason = None
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
        raise AppException(
            "VOLUNTEER_GROUP_LOCKED",
            "志愿组已被另一条企业拟接收决定锁定",
            details={"lockedApplicationId": str(group.locked_application_id or "")},
            http_status=409,
        )
    hours = int(teacher_confirm_sla_hours or _DEFAULT_TEACHER_CONFIRM_SLA_HOURS)
    if hours < 1 or hours > 168:
        raise AppException("VALIDATION_ERROR", "teacherConfirmSlaHours 必须在 1-168 小时")
    before = group.status
    group.status = "LOCKED"
    group.locked_at = current
    group.locked_application_id = _as_id(application_id)
    group.locked_by_decision_id = _as_id(decision_id)
    group.teacher_confirm_deadline = current + timedelta(hours=hours)
    group.unlock_requested_at = None
    group.unlock_request_reason = None
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
    _notify_lock_in_tx(db, group=group, decision_id=decision_id)


def request_unlock_in_tx(db, *, group: InternshipVolunteerGroup, reason: str, user=None, now: datetime | None = None) -> None:
    text = str(reason or "").strip()
    if len(text) < 2:
        raise AppException("VALIDATION_ERROR", "申请改志愿必须填写原因")
    current = now or datetime.utcnow()
    lazy_release_expired_lock_in_tx(db, group=group, tenant_id=group.tenant_id, now=current, user=user)
    if group.status != "LOCKED":
        raise AppException("DATA_CONFLICT", "仅企业拟接收锁定中的志愿组可申请改志愿")
    group.unlock_requested_at = current
    group.unlock_request_reason = text[:500]
    group.version = int(group.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="STUDENT_REQUEST_VOLUNTEER_UNLOCK",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status="LOCKED",
        after_status="LOCKED",
        new_version=group.version,
        reason=text,
        detail={"campaignId": str(group.campaign_id)},
    )
    _message_in_tx(
        db, tenant_id=group.tenant_id, receiver_user_id=_advisor_user_id_in_tx(db, group),
        title="学生申请修改已锁定志愿",
        content="学生已提交改志愿申请，请选择继续确认当前岗位或解除企业确认锁。",
        source_biz_id=group.locked_by_decision_id,
        action_key="INTERNSHIP_STUDENT_UNLOCK_REQUEST",
        action_params={"campaignId": str(group.campaign_id), "volunteerGroupId": str(group.id)},
    )


def supersede_group_active_decisions_in_tx(db, *, group: InternshipVolunteerGroup, reason: str, user=None) -> int:
    """Invalidate prior material-bound enterprise decisions before a student changes/resubmits slots."""
    from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision

    decisions = list(db.scalars(select(InternshipEnterpriseApplicationDecision).where(
        InternshipEnterpriseApplicationDecision.tenant_id == group.tenant_id,
        InternshipEnterpriseApplicationDecision.volunteer_group_id == group.id,
        InternshipEnterpriseApplicationDecision.effect_status == "ACTIVE",
        InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
    ).order_by(InternshipEnterpriseApplicationDecision.id).with_for_update()).all())
    if not decisions:
        return 0
    for decision in decisions:
        if decision.decision_status == "ACCEPT_INTENT":
            raise AppException("VOLUNTEER_GROUP_LOCKED", "存在有效企业拟接收决定，不能直接改志愿", http_status=409)
        _set_effect(decision, effect_status="SUPERSEDED", reason=reason)
        _message_in_tx(
            db, tenant_id=group.tenant_id, receiver_user_id=decision.decided_by_user_id,
            title="学生志愿已变更",
            content="学生已调整并重新提交志愿，您基于旧投递版本的处理结果已失效，请以最新材料为准。",
            source_biz_id=decision.id,
            action_key="INTERNSHIP_VOLUNTEERS_CHANGED",
            action_params={"campaignId": str(group.campaign_id), "volunteerGroupId": str(group.id)},
        )
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_VOLUNTEER_GROUP",
        target_id=group.id,
        action="SUPERSEDE_ENTERPRISE_DECISIONS_FOR_VOLUNTEER_CHANGE",
        user=user,
        batch_id=group.batch_id,
        internship_id=group.record_id,
        before_status=group.status,
        after_status=group.status,
        new_version=int(group.version or 0),
        reason=reason,
        detail={"decisionIds": [str(item.id) for item in decisions]},
    )
    return len(decisions)


def teacher_request_revision_in_tx(
    db,
    *,
    group: InternshipVolunteerGroup,
    reason: str,
    user=None,
    now: datetime | None = None,
    release_reason_code: str = "TEACHER_REQUEST_REVISION",
) -> None:
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
    decision = _locked_decision_in_tx(db, group, lock=True) if before == "LOCKED" else None
    if decision and decision.effect_status == "ACTIVE":
        _set_effect(decision, effect_status="SUPERSEDED", reason=release_reason_code)
    group.status = "NEEDS_REVISION"
    group.revision_requested_at = current
    group.revision_reason = text[:500]
    if before == "LOCKED":
        group.released_at = current
        group.release_reason = release_reason_code
        group.released_by_user_id = _actor_user_id(user)
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
            "releaseReason": group.release_reason,
            "decisionEffect": decision.effect_status if decision else None,
        },
    )
    if before == "LOCKED":
        params = {"campaignId": str(group.campaign_id), "volunteerGroupId": str(group.id)}
        _message_in_tx(
            db, tenant_id=group.tenant_id, receiver_user_id=_student_user_id_in_tx(db, group),
            title="学校已解除企业确认锁",
            content="学校已允许你修改志愿，请根据退回原因调整后重新提交。",
            source_biz_id=group.locked_by_decision_id, action_key="INTERNSHIP_VOLUNTEER_UNLOCKED", action_params=params,
        )
        _message_in_tx(
            db, tenant_id=group.tenant_id,
            receiver_user_id=(decision.decided_by_user_id if decision else None),
            title="学校已释放本次拟接收",
            content="学校已解除该学生的企业确认锁，原拟接收结果已失效。",
            source_biz_id=group.locked_by_decision_id, action_key="INTERNSHIP_ACCEPT_INTENT_SUPERSEDED", action_params=params,
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


def group_dict(group: InternshipVolunteerGroup) -> dict:
    return {
        "id": str(group.id),
        "recordId": str(group.record_id),
        "studentId": str(group.student_id),
        "batchId": str(group.batch_id),
        "campaignId": str(group.campaign_id),
        "status": group.status,
        "submissionVersion": int(group.submission_version or 0),
        "currentMaterialSnapshotId": str(group.current_material_snapshot_id or ""),
        "lockedApplicationId": str(group.locked_application_id or ""),
        "lockedDecisionId": str(group.locked_by_decision_id or ""),
        "lockedAt": group.locked_at.isoformat() if group.locked_at else None,
        "teacherConfirmDeadline": group.teacher_confirm_deadline.isoformat() if group.teacher_confirm_deadline else None,
        "releasedAt": group.released_at.isoformat() if group.released_at else None,
        "releaseReason": group.release_reason,
        "unlockRequestedAt": group.unlock_requested_at.isoformat() if group.unlock_requested_at else None,
        "unlockRequestReason": group.unlock_request_reason,
        "revisionReason": group.revision_reason,
        "version": int(group.version or 0),
    }


def get_my_group(*, user: dict, campaign_id: int) -> dict:
    from app.modules.internship.services import internship_student_profile_service as profile_svc

    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.campaign_id == _as_id(campaign_id),
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).with_for_update())
        if not group:
            return {"exists": False, "campaignId": str(campaign_id), "status": "DRAFT", "version": 0}
        changed = lazy_release_expired_lock_in_tx(db, group=group, tenant_id=tenant_id, user=user)
        if changed:
            db.commit()
        return {"exists": True, **group_dict(group)}


def request_my_unlock(*, user: dict, campaign_id: int, reason: str) -> dict:
    from app.modules.internship.services import internship_student_profile_service as profile_svc

    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.campaign_id == _as_id(campaign_id),
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).with_for_update())
        if not group:
            raise not_found("当前招聘季尚无志愿组")
        request_unlock_in_tx(db, group=group, reason=reason, user=user)
        db.commit()
        return group_dict(group)


def teacher_release_group_lock(*, group_id: int, campaign_id: int, reason: str, user: dict) -> dict:
    from app.models import InternshipRecord, StudentProfile
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope

    tenant_id = _tid()
    with session() as db:
        group = _get_group_in_tx(db, tenant_id=tenant_id, group_id=group_id, lock=True)
        if group.campaign_id != _as_id(campaign_id):
            raise not_found("志愿组不属于当前招聘季")
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == group.record_id,
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.is_deleted.is_(False),
        ))
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == group.student_id,
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        ))
        if not record or not student:
            raise not_found("志愿组关联学生实习记录不存在")
        if not _rec_in_scope(_current_scope(user), db, record, student):
            raise no_permission("该学生不在当前教师数据范围内")
        teacher_request_revision_in_tx(
            db,
            group=group,
            reason=reason,
            user=user,
            release_reason_code="TEACHER_UNLOCK_RELEASE",
        )
        db.commit()
        return group_dict(group)
