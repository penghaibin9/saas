"""Enterprise decision authority over applications owned by the current EnterpriseContext."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipPosition
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_volunteer_group_service as group_svc

_ALLOWED = {
    "PENDING": {"INTERESTED", "INTERVIEW", "ACCEPT_INTENT", "REJECTED"},
    "INTERESTED": {"INTERVIEW", "ACCEPT_INTENT", "REJECTED"},
    "INTERVIEW": {"ACCEPT_INTENT", "REJECTED"},
    "ACCEPT_INTENT": {"REJECTED"},
    "REJECTED": set(),
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


def expire_effect_if_needed_in_tx(decision: InternshipEnterpriseApplicationDecision, *, now: datetime | None = None) -> bool:
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


def set_decision_in_tx(db, *, context, application_id: int, status: str, reason: str | None = None, interview_at=None, interview_note: str | None = None):
    target = str(status or "").upper()
    if target not in {"INTERESTED", "INTERVIEW", "ACCEPT_INTENT", "REJECTED"}:
        raise AppException("VALIDATION_ERROR", "企业决定状态非法")
    application, position = _owned_application_in_tx(db, context=context, application_id=application_id, lock=True)
    if application.status == "APPROVED":
        raise AppException("DATA_CONFLICT", "学校已正式批准落岗，企业不能反向修改决定")
    if application.status not in {"PENDING_REVIEW", "DRAFT"}:
        raise AppException("DATA_CONFLICT", "当前申请状态不可写企业决定")
    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.tenant_id == context.tenant_id,
        InternshipVolunteerGroup.record_id == application.record_id,
        InternshipVolunteerGroup.campaign_id == context.campaign_id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update())
    if not group or group.current_material_snapshot_id != application.material_snapshot_id:
        raise AppException("DATA_CONFLICT", "申请不是当前提交版本，不能覆盖历史企业决定")
    decision = db.scalar(select(InternshipEnterpriseApplicationDecision).where(
        InternshipEnterpriseApplicationDecision.tenant_id == context.tenant_id,
        InternshipEnterpriseApplicationDecision.application_id == application.id,
        InternshipEnterpriseApplicationDecision.material_snapshot_id == application.material_snapshot_id,
        InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
    ).with_for_update())
    if decision is None:
        decision = InternshipEnterpriseApplicationDecision(
            tenant_id=context.tenant_id, application_id=application.id, volunteer_group_id=group.id,
            campaign_id=context.campaign_id, batch_id=context.batch_id, company_id=context.company_id,
            position_id=position.id, material_snapshot_id=application.material_snapshot_id,
            submission_version=group.submission_version, decision_status="PENDING", effect_status="ACTIVE",
        )
        db.add(decision)
        db.flush()
    expire_effect_if_needed_in_tx(decision)
    if decision.effect_status in {"CONSUMED", "SUPERSEDED"}:
        raise AppException("DATA_CONFLICT", "该企业决定已被消费或替代，不能覆盖历史事实")
    current = decision.decision_status
    if target == current and decision.effect_status == "ACTIVE":
        return decision
    if target not in _ALLOWED.get(current, set()):
        raise AppException("DATA_CONFLICT", f"企业决定不能从 {current} 变更为 {target}")
    text = str(reason or "").strip()
    if current == "ACCEPT_INTENT" and target == "REJECTED" and len(text) < 2:
        raise AppException("VALIDATION_ERROR", "撤回拟接收必须填写原因")
    now = datetime.utcnow()
    decision.decision_status = target
    decision.effect_status = "ACTIVE"
    decision.superseded_reason = None
    decision.decision_reason = text or None
    decision.interview_at = interview_at if target == "INTERVIEW" else decision.interview_at
    decision.interview_note = str(interview_note or "").strip() or decision.interview_note
    decision.decided_by_member_id = context.member_id
    decision.decided_by_user_id = context.user_id
    decision.decided_at = now
    decision.version = int(decision.version or 0) + 1
    if target == "ACCEPT_INTENT":
        campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.id == context.campaign_id,
            InternshipRecruitmentCampaign.tenant_id == context.tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        ))
        if not campaign:
            raise AppException("DATA_CONFLICT", "招聘季已不存在，不能拟接收")
        decision.valid_until = min(
            value for value in (campaign.school_confirm_end_at, campaign.enterprise_access_end_at)
            if value is not None
        ) if any(value is not None for value in (campaign.school_confirm_end_at, campaign.enterprise_access_end_at)) else None
        group_svc.lock_for_accept_intent_in_tx(
            db, group=group, application_id=application.id, decision_id=decision.id,
            teacher_confirm_sla_hours=campaign.teacher_confirm_sla_hours, now=now,
        )
        if decision.valid_until and group.teacher_confirm_deadline and group.teacher_confirm_deadline > decision.valid_until:
            group.teacher_confirm_deadline = decision.valid_until
    elif current == "ACCEPT_INTENT" and target == "REJECTED":
        decision.effect_status = "SUPERSEDED"
        decision.superseded_reason = text
        if group.status == "LOCKED" and group.locked_by_decision_id == decision.id:
            group_svc.teacher_request_revision_in_tx(db, group=group, reason=text, now=now)
    db.flush()
    return decision
