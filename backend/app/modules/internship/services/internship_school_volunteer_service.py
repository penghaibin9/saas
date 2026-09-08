"""School projections of canonical volunteer groups, never legacy applications.

Scope and pagination are applied before loading materials. Reads do not release expired
locks: the stored state and the elapsed deadline are returned separately for the reviewer.
"""
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipPosition, InternshipRecord, StudentProfile
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services.internship_application_material_snapshot_service import snapshot_public_dict
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services.internship_volunteer_group_service import group_dict
from app.services.db_service import _as_id, _tid, session
from app.modules.internship.services.internship_version import extract_expected_version

_STATUSES = {"DRAFT", "SUBMITTED", "LOCKED", "NEEDS_REVISION", "APPROVED", "CLOSED"}


def _version(row, expected, label):
    version = extract_expected_version({"expectedVersion": expected})
    if int(row.version or 0) != version:
        raise AppException("DATA_CONFLICT", f"{label}已变化，请刷新后重新核对", http_status=409)


def _lock_review(db, *, campaign_id, group_id, user, expected_group_version,
                 expected_record_version, expected_batch_id=None):
    campaign = _campaign(db, campaign_id, expected_batch_id)
    found = db.execute(_query(campaign.id, user).where(
        InternshipVolunteerGroup.id == _as_id(group_id),
        InternshipVolunteerGroup.batch_id == campaign.batch_id,
    )).first()
    if not found:
        raise not_found("志愿组不存在或不在当前数据范围内")
    initial_group, initial_record, student = found
    # Do not FOR UPDATE the joined projection: MySQL could lock the group first.
    record = db.scalar(apply_internship_record_scope(select(InternshipRecord).where(
        InternshipRecord.id == initial_record.id, InternshipRecord.tenant_id == _tid(),
        InternshipRecord.student_id == student.id, InternshipRecord.batch_id == campaign.batch_id,
        InternshipRecord.is_deleted.is_(False),
    ), user).with_for_update().execution_options(populate_existing=True))
    if not record:
        raise not_found("实习记录已变化或不在当前数据范围内")
    group = db.scalar(select(InternshipVolunteerGroup).where(
        InternshipVolunteerGroup.id == initial_group.id, InternshipVolunteerGroup.tenant_id == _tid(),
        InternshipVolunteerGroup.record_id == record.id, InternshipVolunteerGroup.student_id == record.student_id,
        InternshipVolunteerGroup.batch_id == campaign.batch_id, InternshipVolunteerGroup.campaign_id == campaign.id,
        InternshipVolunteerGroup.is_deleted.is_(False),
    ).with_for_update().execution_options(populate_existing=True))
    if not group:
        raise not_found("志愿组已变化，请刷新后重试")
    _version(record, expected_record_version, "实习记录")
    _version(group, expected_group_version, "志愿组")
    if campaign.status not in {"OPEN", "FROZEN"}:
        raise AppException("DATA_CONFLICT", "招聘季已关闭或尚未开放，不能办理志愿")
    if record.status not in {"PREPARING", "READY"} or record.position_id or record.destination_type == "SELF_ARRANGED":
        raise AppException("DATA_CONFLICT", "学生已落实去向或进入后续实习阶段，不能重复人岗确认")
    if group.status not in {"SUBMITTED", "LOCKED"}:
        raise AppException("DATA_CONFLICT", "仅已提交或拟接收的志愿可办理")
    return campaign, group, record


def return_group(*, campaign_id, group_id, user, reason, expected_group_version,
                 expected_record_version, expected_batch_id=None):
    from app.modules.internship.services import internship_volunteer_group_service as group_svc
    text = str(reason or "").strip()
    if not 2 <= len(text) <= 500:
        raise AppException("VALIDATION_ERROR", "请填写 2～500 字的退回原因")
    with session() as db:
        _, group, record = _lock_review(db, campaign_id=campaign_id, group_id=group_id, user=user,
            expected_group_version=expected_group_version, expected_record_version=expected_record_version,
            expected_batch_id=expected_batch_id)
        # Preserve the school's explanation even if an expired lock is released first.
        group_svc.teacher_request_revision_in_tx(db, group=group, reason=text, user=user, notify=False)
        from app.modules.internship.services.internship_volunteer_notification_service import emit_school_result_in_tx
        outbox_ids = emit_school_result_in_tx(db, group=group, record=record)
        db.commit()
    from app.services.message_event_outbox_service import try_process_pending_outbox
    if outbox_ids:
        try_process_pending_outbox(outbox_ids=outbox_ids, worker_id="school-volunteer-return")
    return get_group(campaign_id=campaign_id, group_id=group_id, user=user, expected_batch_id=expected_batch_id)


def confirm_group(*, campaign_id, group_id, application_id, user, expected_group_version,
                  expected_record_version, expected_application_version, expected_batch_id=None):
    from app.modules.internship.services import internship_student_service as student_svc
    from app.modules.internship.services import internship_audit_service
    with session() as db:
        campaign, group, record = _lock_review(db, campaign_id=campaign_id, group_id=group_id, user=user,
            expected_group_version=expected_group_version, expected_record_version=expected_record_version,
            expected_batch_id=expected_batch_id)
        applications = list(db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == record.id,
            InternshipApplication.student_id == record.student_id, InternshipApplication.batch_id == campaign.batch_id,
            InternshipApplication.campaign_id == campaign.id, InternshipApplication.application_type == "POSITION",
            InternshipApplication.is_deleted.is_(False),
        ).order_by(InternshipApplication.volunteer_no, InternshipApplication.id).with_for_update()
          .execution_options(populate_existing=True)))
        chosen = next((a for a in applications if a.id == _as_id(application_id)), None)
        if not chosen:
            raise not_found("所选志愿不属于该学生当前招聘季")
        _version(chosen, expected_application_version, "所选志愿")
        snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
            InternshipApplicationMaterialSnapshot.id == group.current_material_snapshot_id,
            InternshipApplicationMaterialSnapshot.tenant_id == _tid(),
            InternshipApplicationMaterialSnapshot.volunteer_group_id == group.id,
            InternshipApplicationMaterialSnapshot.student_id == record.student_id,
            InternshipApplicationMaterialSnapshot.batch_id == campaign.batch_id,
            InternshipApplicationMaterialSnapshot.campaign_id == campaign.id,
            InternshipApplicationMaterialSnapshot.submission_version == group.submission_version,
        ))
        if not snapshot or chosen.material_snapshot_id != snapshot.id or chosen.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "所选志愿不是当前有效投递，请刷新材料后重试")
        position = db.scalar(select(InternshipPosition).where(
            InternshipPosition.id == chosen.position_id, InternshipPosition.tenant_id == _tid(),
            InternshipPosition.campaign_id == campaign.id, InternshipPosition.batch_id == record.batch_id,
            InternshipPosition.is_deleted.is_(False),
        ))
        if not position:
            raise AppException("DATA_CONFLICT", "岗位已不可用或不属于当前招聘季")
        if record.eligibility_status != "QUALIFIED":
            raise AppException("DATA_CONFLICT", "学生当前实习资格未通过，不能确认岗位")
        if group.status == "LOCKED" and (group.locked_application_id != chosen.id or
                not group.teacher_confirm_deadline or group.teacher_confirm_deadline <= datetime.utcnow()):
            raise AppException("DATA_CONFLICT", "拟接收岗位不匹配或确认已超时，请先退回修订")
        if not record.advisor_user_id:
            raise AppException("DATA_CONFLICT", "请先为学生分配校内指导教师")
        student_svc.assign_position_in_tx(db, record, chosen.position_id, expected_record_version, user=user)
        from app.modules.internship.services import internship_volunteer_group_service as group_svc
        for decision in db.scalars(select(InternshipEnterpriseApplicationDecision).where(
            InternshipEnterpriseApplicationDecision.tenant_id == _tid(),
            InternshipEnterpriseApplicationDecision.volunteer_group_id == group.id,
            InternshipEnterpriseApplicationDecision.application_id != chosen.id,
            InternshipEnterpriseApplicationDecision.effect_status == "ACTIVE",
            InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
        ).order_by(InternshipEnterpriseApplicationDecision.id).with_for_update()):
            group_svc._set_effect(decision, effect_status="SUPERSEDED", reason="SCHOOL_CONFIRMED_OTHER_VOLUNTEER")
        # The assignment authority owns capacity, placement snapshot and selected application/group.
        # Close only siblings in this canonical group; legacy and other rounds remain distinct.
        for application in applications:
            if application.id == chosen.id or application.status != "PENDING_REVIEW":
                continue
            application.status = "CANCELLED"
            application.review_comment = "学校已确认本组其他志愿"
            application.version = int(application.version or 0) + 1
            internship_audit_service.add_audit(db, target_type="INTERNSHIP_APPLICATION",
                target_id=application.id, action="CANCEL_SIBLING_AFTER_SCHOOL_CONFIRM", user=user,
                batch_id=record.batch_id, internship_id=record.id, before_status="PENDING_REVIEW",
                after_status=application.status, new_version=application.version,
                detail={"selectedApplicationId": str(chosen.id), "campaignId": str(campaign.id)})
        from app.modules.internship.services.internship_volunteer_notification_service import emit_school_result_in_tx
        outbox_ids = emit_school_result_in_tx(db, group=group, record=record, selected_application_id=chosen.id)
        db.commit()
    from app.services.message_event_outbox_service import try_process_pending_outbox
    if outbox_ids:
        try_process_pending_outbox(outbox_ids=outbox_ids, worker_id="school-volunteer-confirm")
    return get_group(campaign_id=campaign_id, group_id=group_id, user=user, expected_batch_id=expected_batch_id)


def review_context(*, batch_id, user):
    """Only rounds in the teacher's actual assigned cohort; no recruitment-admin permission needed."""
    with session() as db:
        records = apply_internship_record_scope(select(InternshipRecord.batch_id).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == _as_id(batch_id),
        ), user)
        rows = db.scalars(select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.tenant_id == _tid(),
            InternshipRecruitmentCampaign.is_deleted.is_(False),
            InternshipRecruitmentCampaign.batch_id.in_(records),
        ).order_by(InternshipRecruitmentCampaign.round_no.desc(), InternshipRecruitmentCampaign.id.desc()))
        return {"items": [{"id": str(row.id), "batchId": str(row.batch_id),
            "name": row.campaign_name, "status": row.status,
            "schoolConfirmStartAt": row.school_confirm_start_at.isoformat() if row.school_confirm_start_at else None,
            "schoolConfirmEndAt": row.school_confirm_end_at.isoformat() if row.school_confirm_end_at else None,
            "enterpriseConfirmRequired": bool(row.enterprise_confirm_required)} for row in rows]}


def _campaign(db, campaign_id, expected_batch_id=None):
    row = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == _as_id(campaign_id),
        InternshipRecruitmentCampaign.tenant_id == _tid(),
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not row or (expected_batch_id is not None and row.batch_id != _as_id(expected_batch_id)):
        raise not_found("招聘季不存在")
    return row


def _query(campaign_id, user):
    group, record, student = InternshipVolunteerGroup, InternshipRecord, StudentProfile
    query = select(group, record, student).join(record, and_(
        record.id == group.record_id, record.tenant_id == group.tenant_id,
        record.batch_id == group.batch_id, record.student_id == group.student_id,
        record.is_deleted.is_(False),
    )).join(student, and_(
        student.id == group.student_id, student.tenant_id == group.tenant_id,
        student.is_deleted.is_(False),
    )).where(group.tenant_id == _tid(), group.campaign_id == _as_id(campaign_id),
             group.is_deleted.is_(False))
    return apply_internship_record_scope(query, user)


def _row(group, record, student, *, now):
    deadline = group.teacher_confirm_deadline
    return {
        **group_dict(group),
        "studentName": student.real_name, "studentNo": student.student_no,
        "advisorUserId": str(record.advisor_user_id or ""),
        "advisorName": record.advisor_name or "",
        "recordVersion": int(record.version or 0), "recordStatus": record.status,
        "eligibilityStatus": record.eligibility_status,
        "positionId": str(record.position_id or ""),
        "positionName": record.position_name or "", "enterpriseName": record.enterprise_name or "",
        "submittedAt": group.submitted_at.isoformat() if group.submitted_at else None,
        "approvedAt": group.approved_at.isoformat() if group.approved_at else None,
        "lockExpired": bool(group.status == "LOCKED" and deadline and deadline <= now),
    }


def list_groups(*, campaign_id, user, status="PENDING", keyword=None, page=1, page_size=20,
                expected_batch_id=None):
    if status not in _STATUSES | {"PENDING", "ALL"}:
        raise AppException("VALIDATION_ERROR", "志愿组状态不正确")
    if page < 1 or not 1 <= page_size <= 100:
        raise AppException("VALIDATION_ERROR", "分页参数不正确")
    with session() as db:
        campaign = _campaign(db, campaign_id, expected_batch_id)
        query = _query(campaign.id, user).where(InternshipVolunteerGroup.batch_id == campaign.batch_id)
        if status == "PENDING":
            query = query.where(InternshipVolunteerGroup.status.in_(("SUBMITTED", "LOCKED")))
        elif status != "ALL":
            query = query.where(InternshipVolunteerGroup.status == status)
        if keyword and keyword.strip():
            term = keyword.strip()
            query = query.where(or_(StudentProfile.real_name.contains(term, autoescape=True),
                                    StudentProfile.student_no.contains(term, autoescape=True)))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        group = InternshipVolunteerGroup
        query = query.order_by(
            case((and_(group.status == "LOCKED", group.unlock_requested_at.is_not(None)), 0),
                 (group.status == "LOCKED", 1), else_=2),
            group.teacher_confirm_deadline.asc(), group.submitted_at.asc(), group.id.asc(),
        ).offset((page - 1) * page_size).limit(page_size)
        now = datetime.utcnow()
        return {"items": [_row(*row, now=now) for row in db.execute(query)],
                "total": total, "page": page, "pageSize": page_size}


def _decision(row):
    return {
        "id": str(row.id), "applicationId": str(row.application_id),
        "materialSnapshotId": str(row.material_snapshot_id),
        "submissionVersion": row.submission_version,
        "status": row.decision_status, "effectStatus": row.effect_status,
        "reason": row.decision_reason, "supersededReason": row.superseded_reason,
        "interviewAt": row.interview_at.isoformat() if row.interview_at else None,
        "decidedAt": row.decided_at.isoformat() if row.decided_at else None,
        "validUntil": row.valid_until.isoformat() if row.valid_until else None,
        "version": int(row.version or 0),
    }


def get_group(*, campaign_id, group_id, user, expected_batch_id=None):
    with session() as db:
        campaign = _campaign(db, campaign_id, expected_batch_id)
        found = db.execute(_query(campaign.id, user).where(
            InternshipVolunteerGroup.id == _as_id(group_id),
            InternshipVolunteerGroup.batch_id == campaign.batch_id,
        )).first()
        if not found:
            raise not_found("志愿组不存在或不在当前数据范围内")
        group, record, student = found
        applications = list(db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(), InternshipApplication.is_deleted.is_(False),
            InternshipApplication.record_id == record.id, InternshipApplication.student_id == student.id,
            InternshipApplication.batch_id == campaign.batch_id, InternshipApplication.campaign_id == campaign.id,
            InternshipApplication.application_type == "POSITION",
        ).order_by(InternshipApplication.volunteer_no.asc(), InternshipApplication.id.asc())))
        positions = {row.id: row for row in db.scalars(select(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
            InternshipPosition.campaign_id == campaign.id,
            InternshipPosition.id.in_([app.position_id for app in applications]),
        ))}
        decisions = list(db.scalars(select(InternshipEnterpriseApplicationDecision).where(
            InternshipEnterpriseApplicationDecision.tenant_id == _tid(),
            InternshipEnterpriseApplicationDecision.is_deleted.is_(False),
            InternshipEnterpriseApplicationDecision.volunteer_group_id == group.id,
            InternshipEnterpriseApplicationDecision.campaign_id == campaign.id,
            InternshipEnterpriseApplicationDecision.batch_id == campaign.batch_id,
            InternshipEnterpriseApplicationDecision.application_id.in_([app.id for app in applications]),
        ).order_by(InternshipEnterpriseApplicationDecision.id.desc())))
        snapshot = db.scalar(select(InternshipApplicationMaterialSnapshot).where(
            InternshipApplicationMaterialSnapshot.id == group.current_material_snapshot_id,
            InternshipApplicationMaterialSnapshot.tenant_id == _tid(),
            InternshipApplicationMaterialSnapshot.volunteer_group_id == group.id,
            InternshipApplicationMaterialSnapshot.student_id == student.id,
            InternshipApplicationMaterialSnapshot.campaign_id == campaign.id,
            InternshipApplicationMaterialSnapshot.batch_id == campaign.batch_id,
            InternshipApplicationMaterialSnapshot.submission_version == group.submission_version,
        )) if group.current_material_snapshot_id else None
        volunteers = []
        for app in applications:
            position = positions.get(app.position_id)
            current = next((d for d in decisions if d.application_id == app.id
                            and d.position_id == app.position_id
                            and d.material_snapshot_id == group.current_material_snapshot_id
                            and d.submission_version == group.submission_version), None)
            volunteers.append({
                "id": str(app.id), "volunteerNo": app.volunteer_no,
                "positionId": str(app.position_id or ""),
                "positionName": position.title if position else app.position_name or "岗位已不可用",
                "companyName": position.company_name if position else app.company_name or "",
                "positionAvailable": bool(position and position.status == "PUBLISHED"),
                "applicationStatement": app.application_statement or "", "status": app.status,
                "version": int(app.version or 0), "materialSnapshotId": str(app.material_snapshot_id or ""),
                "currentSubmission": bool(snapshot and app.material_snapshot_id == snapshot.id),
                "enterpriseDecision": _decision(current) if current else None,
            })
        return {
            **_row(group, record, student, now=datetime.utcnow()),
            "campaignName": campaign.campaign_name,
            "enterpriseConfirmRequired": bool(campaign.enterprise_confirm_required),
            "volunteers": volunteers,
            "material": snapshot_public_dict(snapshot) if snapshot else None,
            "decisionHistory": [_decision(d) for d in decisions],
        }
