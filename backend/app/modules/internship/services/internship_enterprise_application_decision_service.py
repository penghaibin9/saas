"""Enterprise decision authority over applications owned by the current EnterpriseContext."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.core.field_crypto import decrypt_field
from app.models import InternshipApplication, InternshipPosition, StudentContact
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_audit_service
from app.modules.internship.services import internship_recruitment_window_guard as window_guard
from app.modules.internship.services import internship_volunteer_group_service as group_svc

_ALLOWED = {
    "PENDING": {"INTERESTED", "INTERVIEW", "ACCEPT_INTENT", "REJECTED"},
    "INTERESTED": {"INTERVIEW", "ACCEPT_INTENT", "REJECTED"},
    "INTERVIEW": {"ACCEPT_INTENT", "REJECTED"},
    "ACCEPT_INTENT": {"REJECTED"},
    "REJECTED": set(),
}


def _actor(context) -> dict:
    return {
        "userId": f"db-{context.user_id}",
        "realName": str((context.claims or {}).get("realName") or "企业成员"),
        "userType": "ENTERPRISE_MENTOR",
        "currentRoleCode": f"ENTERPRISE_{context.member_role}",
    }


def _owned_application_in_tx(db, *, context, application_id: int, lock: bool = False):
    stmt = select(InternshipApplication, InternshipPosition).join(
        InternshipPosition, InternshipPosition.id == InternshipApplication.position_id
    ).where(
        InternshipApplication.id == int(application_id),
        InternshipApplication.tenant_id == context.tenant_id,
        InternshipApplication.batch_id == context.batch_id,
        InternshipApplication.material_snapshot_id.is_not(None),
        InternshipApplication.is_deleted.is_(False),
        InternshipPosition.tenant_id == context.tenant_id,
        InternshipPosition.campaign_id == context.campaign_id,
        InternshipPosition.company_id == context.company_id,
        InternshipPosition.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    pair = db.execute(stmt).first()
    if not pair:
        raise not_found("申请不存在或不属于当前企业")
    return pair[0], pair[1]


def _campaign_in_tx(db, *, context) -> InternshipRecruitmentCampaign:
    campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == context.campaign_id,
        InternshipRecruitmentCampaign.tenant_id == context.tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not campaign:
        raise AppException("DATA_CONFLICT", "招聘季已不存在")
    return campaign


def _assert_decision_write_window(
    campaign: InternshipRecruitmentCampaign,
    *,
    current_status: str,
    target_status: str,
    now: datetime,
) -> None:
    # A withdrawal is a safety action for an existing ACCEPT_INTENT. It is allowed while the
    # campaign is still OPEN/FROZEN; school approval is checked separately on the application.
    if current_status == "ACCEPT_INTENT" and target_status == "REJECTED":
        if campaign.status not in {"OPEN", "FROZEN"}:
            raise AppException("DATA_CONFLICT", "招聘季已关闭，企业不能再撤回拟接收")
        return
    window_guard.assert_campaign_operation_window(campaign, "ENTERPRISE_DECISION", now=now)


def list_owned_applications_in_tx(
    db,
    *,
    context,
    page: int = 1,
    page_size: int = 20,
    position_id: int | None = None,
    decision_status: str | None = None,
) -> tuple[list[dict], int]:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    query = select(
        InternshipApplication,
        InternshipPosition,
        InternshipApplicationMaterialSnapshot,
        InternshipEnterpriseApplicationDecision,
    ).join(
        InternshipPosition, InternshipPosition.id == InternshipApplication.position_id,
    ).join(
        InternshipApplicationMaterialSnapshot,
        InternshipApplicationMaterialSnapshot.id == InternshipApplication.material_snapshot_id,
    ).outerjoin(
        InternshipEnterpriseApplicationDecision,
        (InternshipEnterpriseApplicationDecision.tenant_id == context.tenant_id)
        & (InternshipEnterpriseApplicationDecision.application_id == InternshipApplication.id)
        & (InternshipEnterpriseApplicationDecision.material_snapshot_id == InternshipApplication.material_snapshot_id)
        & InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
    ).where(
        InternshipApplication.tenant_id == context.tenant_id,
        InternshipApplication.batch_id == context.batch_id,
        InternshipApplication.status == "PENDING_REVIEW",
        InternshipApplication.material_snapshot_id.is_not(None),
        InternshipApplication.is_deleted.is_(False),
        InternshipPosition.tenant_id == context.tenant_id,
        InternshipPosition.campaign_id == context.campaign_id,
        InternshipPosition.company_id == context.company_id,
        InternshipPosition.is_deleted.is_(False),
        InternshipApplicationMaterialSnapshot.tenant_id == context.tenant_id,
    )
    if position_id is not None:
        query = query.where(InternshipPosition.id == int(position_id))
    if decision_status:
        target = str(decision_status).upper()
        if target == "PENDING":
            query = query.where(
                (InternshipEnterpriseApplicationDecision.id.is_(None))
                | (InternshipEnterpriseApplicationDecision.decision_status == "PENDING")
            )
        elif target in _ALLOWED:
            query = query.where(InternshipEnterpriseApplicationDecision.decision_status == target)
        else:
            raise AppException("VALIDATION_ERROR", "decisionStatus 非法")

    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.execute(
        query.order_by(
            InternshipApplication.submitted_at.desc(),
            InternshipApplication.id.desc(),
        ).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items: list[dict] = []
    for application, position, snapshot, decision in rows:
        school = dict(snapshot.school_fact_snapshot_json or {})
        items.append({
            "applicationId": str(application.id),
            "volunteerNo": int(application.volunteer_no or 0),
            "positionId": str(position.id),
            "positionTitle": position.title,
            "student": {
                "realName": school.get("realName") or "",
                "collegeName": school.get("collegeName") or "",
                "majorName": school.get("majorName") or "",
                "grade": school.get("grade") or "",
            },
            "submissionVersion": int(snapshot.submission_version or 0),
            "materialSnapshotId": str(snapshot.id),
            "submittedAt": application.submitted_at.isoformat() if application.submitted_at else None,
            "decisionStatus": decision.decision_status if decision else "PENDING",
            "effectStatus": decision.effect_status if decision else None,
            "decisionVersion": int(decision.version or 0) if decision else 0,
        })
    return items, total


def material_detail_in_tx(db, *, context, application_id: int) -> dict:
    application, position = _owned_application_in_tx(db, context=context, application_id=application_id)
    snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
        InternshipApplicationMaterialSnapshot.id == application.material_snapshot_id,
        InternshipApplicationMaterialSnapshot.tenant_id == context.tenant_id,
    ))
    if not snapshot:
        raise not_found("投递材料快照不存在")
    return {
        "applicationId": str(application.id),
        "positionId": str(position.id),
        "positionTitle": position.title,
        "applicationStatement": application.application_statement,
        "submissionVersion": snapshot.submission_version,
        "profileSnapshot": snapshot.profile_snapshot_json,
        "schoolFactSnapshot": snapshot.school_fact_snapshot_json,
        "snapshotHash": snapshot.snapshot_hash,
        "contactSharingPolicy": snapshot.contact_sharing_policy,
    }


def expire_effect_if_needed_in_tx(
    decision: InternshipEnterpriseApplicationDecision,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.utcnow()
    if decision.effect_status == "ACTIVE" and decision.valid_until and decision.valid_until <= current:
        decision.effect_status = "EXPIRED"
        decision.superseded_reason = decision.superseded_reason or "VALID_UNTIL_EXPIRED"
        decision.version = int(decision.version or 0) + 1
        return True
    return False


def consume_accept_intent_in_tx(decision: InternshipEnterpriseApplicationDecision) -> None:
    if decision.decision_status != "ACCEPT_INTENT" or decision.effect_status != "ACTIVE":
        raise AppException("DATA_CONFLICT", "企业拟接收决定当前无效，不能用于正式落岗")
    decision.effect_status = "CONSUMED"
    decision.version = int(decision.version or 0) + 1


def _current_decision_in_tx(db, *, context, application: InternshipApplication):
    return db.scalar(select(InternshipEnterpriseApplicationDecision).where(
        InternshipEnterpriseApplicationDecision.tenant_id == context.tenant_id,
        InternshipEnterpriseApplicationDecision.application_id == application.id,
        InternshipEnterpriseApplicationDecision.material_snapshot_id == application.material_snapshot_id,
        InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
    ).with_for_update())


def contact_view_in_tx(db, *, context, application_id: int) -> dict:
    """Reveal current verified contact only after snapshot consent + stage gate; never snapshot PII."""
    application, _position = _owned_application_in_tx(
        db, context=context, application_id=application_id, lock=True,
    )
    if application.status not in {"PENDING_REVIEW", "APPROVED"}:
        raise AppException("NO_PERMISSION", "当前申请状态不允许企业查看联系方式", http_status=403)
    snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
        InternshipApplicationMaterialSnapshot.id == application.material_snapshot_id,
        InternshipApplicationMaterialSnapshot.tenant_id == context.tenant_id,
    ))
    if not snapshot:
        raise not_found("投递材料快照不存在")
    policy = material_svc.normalize_contact_sharing_policy(snapshot.contact_sharing_policy)
    mode = policy["mode"]
    if mode == "MASKED_ONLY":
        raise AppException("NO_PERMISSION", "学生仅授权脱敏联系方式，不能查看完整联系方式", http_status=403)

    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.tenant_id == context.tenant_id,
        InternshipVolunteerGroup.id == snapshot.volunteer_group_id,
        InternshipVolunteerGroup.record_id == application.record_id,
        InternshipVolunteerGroup.campaign_id == context.campaign_id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update())
    if not group:
        raise AppException("DATA_CONFLICT", "投递材料对应志愿组不存在")
    group_svc.lazy_release_expired_lock_in_tx(
        db, group=group, tenant_id=context.tenant_id, user=_actor(context),
    )
    if group.contact_consent_revoked_at is not None:
        raise AppException("NO_PERMISSION", "学生已撤销联系方式共享授权", http_status=403)

    decision = _current_decision_in_tx(db, context=context, application=application)
    if mode == "AFTER_INTERVIEW":
        allowed = bool(
            decision
            and decision.decision_status in {"INTERVIEW", "ACCEPT_INTENT"}
            and decision.effect_status in {"ACTIVE", "CONSUMED"}
        )
    elif mode == "AFTER_ACCEPT_INTENT":
        allowed = bool(
            decision
            and decision.decision_status == "ACCEPT_INTENT"
            and decision.effect_status in {"ACTIVE", "CONSUMED"}
        )
    elif mode == "IMMEDIATE":
        allowed = True
    else:
        allowed = False
    if not allowed:
        raise AppException("NO_PERMISSION", "企业当前处理阶段尚未达到学生授权的联系方式查看条件", http_status=403)

    contacts = list(db.scalars(select(StudentContact).where(
        StudentContact.tenant_id == context.tenant_id,
        StudentContact.student_id == application.student_id,
        StudentContact.contact_type.in_(("PHONE", "EMAIL")),
        StudentContact.verified_status == "VERIFIED",
        StudentContact.is_deleted.is_(False),
    ).order_by(StudentContact.is_primary.desc(), StudentContact.id.desc())).all())
    values: dict[str, str] = {}
    for contact in contacts:
        key = "phone" if contact.contact_type == "PHONE" else "email"
        if key in values or not contact.contact_value_encrypted:
            continue
        if key == "phone" and not policy.get("sharePhone", True):
            continue
        if key == "email" and not policy.get("shareEmail", True):
            continue
        plaintext = decrypt_field(contact.contact_value_encrypted)
        if plaintext:
            values[key] = plaintext

    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_ENTERPRISE_APPLICATION_DECISION",
        target_id=(decision.id if decision else application.id),
        action="CONTACT_VIEW",
        user=_actor(context),
        batch_id=context.batch_id,
        internship_id=group.record_id,
        before_status=(decision.decision_status if decision else "PENDING"),
        after_status=(decision.decision_status if decision else "PENDING"),
        new_version=(int(decision.version or 0) if decision else int(application.version or 0)),
        detail={
            "applicationId": str(application.id),
            "campaignId": str(context.campaign_id),
            "companyId": str(context.company_id),
            "contactMode": mode,
            "revealedTypes": sorted(values),
        },
    )
    db.flush()
    return {"applicationId": str(application.id), "contactMode": mode, **values}


def set_decision_in_tx(
    db,
    *,
    context,
    application_id: int,
    status: str,
    reason: str | None = None,
    interview_at=None,
    interview_note: str | None = None,
):
    target = str(status or "").upper()
    if target not in {"INTERESTED", "INTERVIEW", "ACCEPT_INTENT", "REJECTED"}:
        raise AppException("VALIDATION_ERROR", "企业决定状态非法")
    application, position = _owned_application_in_tx(
        db, context=context, application_id=application_id, lock=True,
    )
    if application.status == "APPROVED":
        raise AppException("DATA_CONFLICT", "学校已正式批准落岗，企业不能反向修改决定")
    if application.status != "PENDING_REVIEW":
        raise AppException("DATA_CONFLICT", "仅当前已提交志愿可写企业决定")

    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.tenant_id == context.tenant_id,
        InternshipVolunteerGroup.record_id == application.record_id,
        InternshipVolunteerGroup.campaign_id == context.campaign_id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update())
    if not group or group.current_material_snapshot_id != application.material_snapshot_id:
        raise AppException("DATA_CONFLICT", "申请不是当前提交版本，不能覆盖历史企业决定")
    group_svc.lazy_release_expired_lock_in_tx(
        db, group=group, tenant_id=context.tenant_id, user=_actor(context),
    )

    decision = _current_decision_in_tx(db, context=context, application=application)
    if decision is None:
        decision = InternshipEnterpriseApplicationDecision(
            tenant_id=context.tenant_id,
            application_id=application.id,
            volunteer_group_id=group.id,
            campaign_id=context.campaign_id,
            batch_id=context.batch_id,
            company_id=context.company_id,
            position_id=position.id,
            material_snapshot_id=application.material_snapshot_id,
            submission_version=group.submission_version,
            decision_status="PENDING",
            effect_status="ACTIVE",
        )
        db.add(decision)
        db.flush()

    now = datetime.utcnow()
    expire_effect_if_needed_in_tx(decision, now=now)
    if decision.effect_status != "ACTIVE":
        raise AppException("DATA_CONFLICT", "该企业决定已失效、替代或消费，不能覆盖历史事实")
    current = decision.decision_status
    if target == current:
        return decision
    if target not in _ALLOWED.get(current, set()):
        raise AppException("DATA_CONFLICT", f"企业决定不能从 {current} 变更为 {target}")

    campaign = _campaign_in_tx(db, context=context)
    _assert_decision_write_window(
        campaign, current_status=current, target_status=target, now=now,
    )
    text = str(reason or "").strip()
    if current == "ACCEPT_INTENT" and target == "REJECTED" and len(text) < 2:
        raise AppException("VALIDATION_ERROR", "撤回拟接收必须填写原因")
    if target == "INTERVIEW" and interview_at is None:
        raise AppException("VALIDATION_ERROR", "记录面试必须填写 interviewAt")

    before_status = current
    action = f"ENTERPRISE_APPLICATION_{target}"
    decision.decision_status = target
    decision.effect_status = "ACTIVE"
    decision.superseded_reason = None
    decision.decision_reason = text or None
    if target == "INTERVIEW":
        decision.interview_at = interview_at
        decision.interview_note = str(interview_note or "").strip() or None
    decision.decided_by_member_id = context.member_id
    decision.decided_by_user_id = context.user_id
    decision.decided_at = now
    decision.version = int(decision.version or 0) + 1

    if target == "ACCEPT_INTENT":
        bounds = [
            value for value in (campaign.school_confirm_end_at, campaign.enterprise_access_end_at)
            if value is not None
        ]
        decision.valid_until = min(bounds) if bounds else None
        if decision.valid_until is not None and decision.valid_until <= now:
            raise AppException("DATA_CONFLICT", "学校确认/企业访问期限已结束，不能再拟接收")
        group_svc.lock_for_accept_intent_in_tx(
            db,
            group=group,
            application_id=application.id,
            decision_id=decision.id,
            teacher_confirm_sla_hours=campaign.teacher_confirm_sla_hours,
            now=now,
            user=_actor(context),
        )
        if decision.valid_until and group.teacher_confirm_deadline and group.teacher_confirm_deadline > decision.valid_until:
            group.teacher_confirm_deadline = decision.valid_until
    elif current == "ACCEPT_INTENT" and target == "REJECTED":
        action = "ENTERPRISE_APPLICATION_WITHDRAW_ACCEPT"
        decision.effect_status = "SUPERSEDED"
        decision.superseded_reason = text
        if group.status == "LOCKED" and group.locked_by_decision_id == decision.id:
            group_svc.teacher_request_revision_in_tx(
                db,
                group=group,
                reason=text,
                now=now,
                user=_actor(context),
                release_reason_code="ENTERPRISE_WITHDRAW_ACCEPT",
            )

    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_ENTERPRISE_APPLICATION_DECISION",
        target_id=decision.id,
        action=action,
        user=_actor(context),
        batch_id=context.batch_id,
        internship_id=group.record_id,
        before_status=before_status,
        after_status=decision.decision_status,
        new_version=decision.version,
        reason=text or None,
        detail={
            "campaignId": str(context.campaign_id),
            "companyId": str(context.company_id),
            "applicationId": str(application.id),
            "materialSnapshotId": str(application.material_snapshot_id),
            "effectStatus": decision.effect_status,
        },
    )
    db.flush()
    return decision


def withdraw_accept_in_tx(db, *, context, application_id: int, reason: str):
    return set_decision_in_tx(
        db,
        context=context,
        application_id=application_id,
        status="REJECTED",
        reason=reason,
    )
