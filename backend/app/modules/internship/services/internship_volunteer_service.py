"""Atomic 1/2/3 volunteer write path over canonical InternshipApplication rows."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipApplication, InternshipPosition, InternshipRecord
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.modules.internship.services import internship_application_material_snapshot_service as material_svc
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc


def save_or_submit_in_tx(db, *, tenant_id: int, student_id: int, record_id: int, campaign_id: int, volunteers: list[dict], expected_group_version: int, submit: bool, consent_version: str | None = None, consent_at: datetime | None = None, contact_sharing_policy: dict | None = None):
    """Lock order is frozen: Record -> VolunteerGroup -> Applications volunteer_no ASC."""
    if not 1 <= len(volunteers) <= 3:
        raise AppException("VALIDATION_ERROR", "志愿必须为 1-3 个")
    slots = [int(v.get("volunteerNo") or 0) for v in volunteers]
    if slots != list(range(1, len(volunteers) + 1)):
        raise AppException("VALIDATION_ERROR", "volunteerNo 必须连续固定为 1/2/3")
    position_ids = [int(v.get("positionId") or 0) for v in volunteers]
    if len(set(position_ids)) != len(position_ids) or any(x <= 0 for x in position_ids):
        raise AppException("VALIDATION_ERROR", "三个志愿岗位不得重复且必须有效")

    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == record_id,
        InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.student_id == student_id,
        InternshipRecord.is_deleted.is_(False),
    ).with_for_update())
    if not record:
        raise not_found("实习记录不存在")
    campaign = db.scalar(select(InternshipRecruitmentCampaign).where(
        InternshipRecruitmentCampaign.id == campaign_id,
        InternshipRecruitmentCampaign.tenant_id == tenant_id,
        InternshipRecruitmentCampaign.is_deleted.is_(False),
    ))
    if not campaign:
        raise not_found("招聘季不存在")
    group = group_svc.get_or_create_group_in_tx(
        db, tenant_id=tenant_id, record_id=record.id, student_id=student_id,
        batch_id=campaign.batch_id, campaign_id=campaign.id,
    )
    group_svc.assert_student_editable_in_tx(db, group=group, tenant_id=tenant_id)
    if int(group.version or 0) != int(expected_group_version):
        raise AppException("DATA_CONFLICT", "志愿组版本已变化，请刷新后重试", http_status=409)

    existing = list(db.scalars(select(InternshipApplication).where(
        InternshipApplication.tenant_id == tenant_id,
        InternshipApplication.record_id == record.id,
        InternshipApplication.application_type == "POSITION",
        InternshipApplication.volunteer_no.in_([1, 2, 3]),
        InternshipApplication.is_deleted.is_(False),
    ).order_by(InternshipApplication.volunteer_no.asc()).with_for_update()).all())
    by_slot = {int(row.volunteer_no): row for row in existing}

    checked = {}
    for item in volunteers:
        position = db.scalar(select(InternshipPosition).where(
            InternshipPosition.id == int(item["positionId"]),
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.is_deleted.is_(False),
        ))
        if not position:
            raise not_found("志愿岗位不存在")
        eligibility_svc.evaluate_position_for_student_in_tx(
            db, tenant_id=tenant_id, record=record, campaign=campaign, position=position,
        )
        checked[int(item["volunteerNo"])] = position

    now = datetime.utcnow()
    for item in volunteers:
        slot = int(item["volunteerNo"])
        p = checked[slot]
        row = by_slot.get(slot)
        if row is None:
            row = InternshipApplication(
                tenant_id=tenant_id, record_id=record.id, student_id=student_id,
                batch_id=campaign.batch_id, application_type="POSITION", volunteer_no=slot,
            )
            db.add(row)
            by_slot[slot] = row
        elif row.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "已批准志愿不能普通修改")
        row.position_id = p.id
        row.company_name = p.company_name
        row.position_name = p.title
        row.work_address = p.work_address or p.work_location
        row.application_statement = str(item.get("applicationStatement") or "").strip() or None
        row.status = "DRAFT"
        row.material_snapshot_id = None
        row.submitted_at = None
        row.version = int(row.version or 0) + 1

    # Slots omitted from a shorter draft are kept as historical rows but withdrawn, never DELETEd.
    for slot, row in by_slot.items():
        if slot > len(volunteers) and row.status not in {"APPROVED", "CANCELLED"}:
            row.status = "WITHDRAWN"
            row.version = int(row.version or 0) + 1

    if submit:
        next_submission = int(group.submission_version or 0) + 1
        snapshot = material_svc.create_material_snapshot_in_tx(
            db, tenant_id=tenant_id, volunteer_group_id=group.id, student_id=student_id,
            campaign_id=campaign.id, submission_version=next_submission,
            consent_version=str(consent_version or ""), consent_at=consent_at,
            contact_sharing_policy=contact_sharing_policy,
        )
        for slot in range(1, len(volunteers) + 1):
            row = by_slot[slot]
            row.material_snapshot_id = snapshot.id
            row.status = "PENDING_REVIEW"
            row.submitted_at = now
        group_svc.mark_submitted_in_tx(
            db, group=group, material_snapshot_id=snapshot.id,
            submission_version=next_submission, now=now,
        )
    else:
        group.status = "DRAFT" if group.status != "NEEDS_REVISION" else "NEEDS_REVISION"
        group.version = int(group.version or 0) + 1

    db.flush()
    return group, [by_slot[i] for i in sorted(by_slot) if i <= len(volunteers)]
