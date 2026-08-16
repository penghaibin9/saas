"""Explicit additive wrapper for the existing assign_position_in_tx Authority.

The existing function remains the only position/capacity writer. This installer replaces that
module binding once at API startup so every existing caller (teacher approval, direct assignment,
formal position change) gets immutable placement evidence in the same DB transaction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.tenant_scoped import tenant_get
from app.models import InternshipApplication, InternshipPosition
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_audit_service
from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc
from app.modules.internship.services import internship_placement_snapshot_service as snapshot_svc
from app.modules.internship.services import internship_recruitment_window_guard as window_guard
from app.modules.internship.services import internship_student_service as student_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc

_INSTALLED = False
_ORIGINAL = None


def _assert_school_confirm_window(campaign: InternshipRecruitmentCampaign, *, now: datetime) -> None:
    window_guard.assert_campaign_operation_window(campaign, "SCHOOL_CONFIRM", now=now)


def _source_for_campaign_in_tx(db, *, record, position, now: datetime):
    if not position.campaign_id:
        return None, None, None, None
    campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == position.campaign_id,
        InternshipRecruitmentCampaign.tenant_id == record.tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not campaign:
        raise AppException("DATA_CONFLICT", "岗位招聘季不存在，不能正式落岗")
    # Every formal placement into a campaign-owned position is a SCHOOL_CONFIRM operation.
    # Direct/manual assignment may omit an application, but it must never bypass the campaign
    # confirmation window or reopen a closed/frozen recruitment season by side effect.
    _assert_school_confirm_window(campaign, now=now)
    application = db.scalar(select(InternshipApplication).where(
        InternshipApplication.tenant_id == record.tenant_id,
        InternshipApplication.record_id == record.id,
        InternshipApplication.batch_id == campaign.batch_id,
        InternshipApplication.campaign_id == campaign.id,
        InternshipApplication.position_id == position.id,
        InternshipApplication.status == "PENDING_REVIEW",
        InternshipApplication.material_snapshot_id.is_not(None),
        InternshipApplication.is_deleted.is_(False),
    ).order_by(InternshipApplication.submitted_at.desc(), InternshipApplication.id.desc()).limit(1))
    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.tenant_id == record.tenant_id,
        InternshipVolunteerGroup.record_id == record.id,
        InternshipVolunteerGroup.campaign_id == campaign.id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update())
    decision = None
    if application and group and group.locked_by_decision_id:
        decision = db.scalar(select(InternshipEnterpriseApplicationDecision).where(
            InternshipEnterpriseApplicationDecision.id == group.locked_by_decision_id,
            InternshipEnterpriseApplicationDecision.tenant_id == record.tenant_id,
            InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
        ).with_for_update())
    if campaign.enterprise_confirm_required:
        if group:
            group_svc.lazy_release_expired_lock_in_tx(db, group=group, tenant_id=record.tenant_id, now=now)
        valid = bool(
            application and group and decision
            and group.status == "LOCKED"
            and group.locked_application_id == application.id
            and group.locked_by_decision_id == decision.id
            and group.current_material_snapshot_id == application.material_snapshot_id
            and group.teacher_confirm_deadline and group.teacher_confirm_deadline > now
            and decision.application_id == application.id
            and decision.campaign_id == campaign.id
            and decision.material_snapshot_id == application.material_snapshot_id
            and decision.decision_status == "ACCEPT_INTENT"
            and decision.effect_status == "ACTIVE"
            and (decision.valid_until is None or decision.valid_until > now)
        )
        if not valid:
            raise AppException("DATA_CONFLICT", "企业尚未确认拟接收，不能正式落岗")
    return campaign, application, group, decision


def _approve_source_application_in_tx(db, *, application, record, campaign, decision, snapshot, user, now: datetime) -> None:
    if not application:
        return
    before = application.status
    if before != "PENDING_REVIEW":
        raise AppException("DATA_CONFLICT", "当前志愿申请状态已变化，不能重复学校确认")
    application.status = "APPROVED"
    application.review_comment = "学校最终确认通过"
    application.reviewed_by_name = str((user or {}).get("realName") or "系统")
    application.reviewed_at = now
    application.version = int(application.version or 0) + 1
    internship_audit_service.add_audit(
        db,
        target_type="INTERNSHIP_APPLICATION",
        target_id=application.id,
        action="SCHOOL_CONFIRM_APPLICATION",
        user=user,
        batch_id=record.batch_id,
        internship_id=record.id,
        before_status=before,
        after_status=application.status,
        new_version=application.version,
        detail={
            "campaignId": str(campaign.id) if campaign else "",
            "positionId": str(snapshot.position_id),
            "placementSnapshotId": str(snapshot.id),
            "enterpriseDecisionId": str(decision.id) if decision else "",
        },
    )


def _wrapped_assign_position_in_tx(db, record, position_id, expected_version, user=None):
    now = datetime.utcnow()
    position = db.scalar(select(InternshipPosition).where(
        InternshipPosition.id == int(position_id),
        InternshipPosition.tenant_id == record.tenant_id,
        InternshipPosition.is_deleted.is_(False),
    ))
    if not position:
        return _ORIGINAL(db, record, position_id, expected_version, user=user)
    campaign, application, group, decision = _source_for_campaign_in_tx(
        db, record=record, position=position, now=now,
    )
    company = tenant_get(db, student_svc.EmpCompany, position.company_id, tenant_id=record.tenant_id)
    batch = tenant_get(db, student_svc.InternshipBatch, record.batch_id, tenant_id=record.tenant_id) if record.batch_id else None
    student = tenant_get(db, student_svc.StudentProfile, record.student_id, tenant_id=record.tenant_id)
    from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
    rights = evaluate_position_publishability(position, company, batch, student, operation="ASSIGN", db=db)
    result = _ORIGINAL(db, record, position_id, expected_version, user=user)
    db.refresh(position)
    snap = snapshot_svc.capture_placement_snapshot_in_tx(
        db,
        record=record,
        position=position,
        company=company,
        rights=rights,
        source_application_id=application.id if application else None,
        source_enterprise_decision_id=decision.id if decision else None,
    )
    if decision:
        decision_svc.consume_accept_intent_in_tx(decision)
    _approve_source_application_in_tx(
        db,
        application=application,
        record=record,
        campaign=campaign,
        decision=decision,
        snapshot=snap,
        user=user,
        now=now,
    )
    # A school-side direct/manual placement to a different campaign position must not silently
    # mark an unrelated submitted volunteer group APPROVED. Only the selected canonical application
    # may close the group.
    if group and application:
        group_svc.teacher_mark_approved_in_tx(db, group=group, user=user, now=now)
    student_svc._trail(db, record.id, "PLACEMENT_SNAPSHOT", {
        "snapshotId": str(snap.id), "snapshotSha256": snap.snapshot_sha256,
        "placementSeq": snap.placement_seq,
        "applicationId": str(application.id) if application else "",
        "enterpriseDecisionId": str(decision.id) if decision else "",
    })
    return result


def install_assignment_snapshot_authority() -> None:
    global _INSTALLED, _ORIGINAL
    if _INSTALLED:
        return
    current = student_svc.assign_position_in_tx
    if getattr(current, "__e_a01_placement_snapshot_wrapped__", False):
        _INSTALLED = True
        return
    _ORIGINAL = current
    _wrapped_assign_position_in_tx.__e_a01_placement_snapshot_wrapped__ = True
    student_svc.assign_position_in_tx = _wrapped_assign_position_in_tx
    _INSTALLED = True
