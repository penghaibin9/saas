"""Owned result reads pinned to a group, including closed recruitment rounds.

Unlike the current selection context, this projection never selects a newer round,
releases a lock, or returns a teacher's internal review fields.
"""
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import not_found
from app.models import InternshipApplication, InternshipBatch, InternshipRecord
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services.internship_student_profile_service import resolve_my_student_id
from app.modules.internship.services.internship_volunteer_service import _application_row
from app.services.db_service import _as_id, _iso, _tid, session


def get_my_result(*, group_id, user):
    tenant_id = _tid()
    student_id = resolve_my_student_id(user)
    with session() as db:
        row = db.execute(select(InternshipVolunteerGroup, InternshipRecruitmentCampaign, InternshipBatch).join(
            InternshipRecord, InternshipRecord.id == InternshipVolunteerGroup.record_id,
        ).join(InternshipRecruitmentCampaign, InternshipRecruitmentCampaign.id == InternshipVolunteerGroup.campaign_id,
        ).join(InternshipBatch, InternshipBatch.id == InternshipVolunteerGroup.batch_id).where(
            InternshipVolunteerGroup.id == _as_id(group_id),
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.is_deleted.is_(False),
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.student_id == student_id,
            InternshipRecord.batch_id == InternshipVolunteerGroup.batch_id,
            InternshipRecord.is_deleted.is_(False),
            InternshipRecruitmentCampaign.tenant_id == tenant_id,
            InternshipRecruitmentCampaign.batch_id == InternshipVolunteerGroup.batch_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
            InternshipBatch.tenant_id == tenant_id,
            InternshipBatch.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("该志愿不存在或不属于本人")
        group, campaign, batch = row
        applications = db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == tenant_id,
            InternshipApplication.student_id == student_id,
            InternshipApplication.record_id == group.record_id,
            InternshipApplication.batch_id == group.batch_id,
            InternshipApplication.campaign_id == group.campaign_id,
            InternshipApplication.volunteer_no.in_([1, 2, 3]),
            InternshipApplication.is_deleted.is_(False),
        ).order_by(InternshipApplication.volunteer_no, InternshipApplication.id))
        return {
            "id": str(group.id), "recordId": str(group.record_id),
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "campaignId": str(campaign.id), "campaignName": campaign.campaign_name,
            "campaignStatus": campaign.status, "status": group.status,
            "version": int(group.version or 0), "submissionVersion": int(group.submission_version or 0),
            "submittedAt": _iso(group.submitted_at), "approvedAt": _iso(group.approved_at),
            "revisionRequestedAt": _iso(group.revision_requested_at),
            "revisionReason": group.revision_reason or "",
            "teacherConfirmDeadline": _iso(group.teacher_confirm_deadline),
            "lockExpired": bool(group.status == "LOCKED" and group.teacher_confirm_deadline
                                and group.teacher_confirm_deadline <= datetime.utcnow()),
            "items": [_application_row(application) for application in applications],
        }
