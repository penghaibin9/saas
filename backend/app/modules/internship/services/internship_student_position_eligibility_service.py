"""Catalog and volunteer submission share one canonical eligibility guard."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import EmpCompany, InternshipBatch, InternshipBatchParticipant, InternshipPosition, StudentProfile
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise, InternshipRecruitmentCampaign
from app.modules.internship.services.internship_position_rights import evaluate_position_publishability


def assert_student_selection_window(campaign: InternshipRecruitmentCampaign, now: datetime | None = None) -> None:
    now = now or datetime.utcnow()
    if campaign.status != "OPEN":
        raise AppException("DATA_CONFLICT", "当前招聘季未开放学生选岗")
    if not campaign.student_select_start_at or not campaign.student_select_end_at:
        raise AppException("DATA_CONFLICT", "招聘季未配置完整学生选岗时间窗")
    if now < campaign.student_select_start_at or now > campaign.student_select_end_at:
        raise AppException("DATA_CONFLICT", "当前不在学生选岗时间窗内")


def evaluate_position_for_student_in_tx(db, *, tenant_id: int, record, campaign, position: InternshipPosition, now=None) -> dict:
    assert_student_selection_window(campaign, now)
    if record.tenant_id != tenant_id or record.batch_id != campaign.batch_id:
        raise AppException("DATA_CONFLICT", "学生实习记录与招聘季不一致")
    if record.eligibility_status != "QUALIFIED":
        raise AppException("NO_PERMISSION", "学生实习资格尚未通过")
    if record.position_id or record.destination_type in {"ASSIGNED", "SELF_ARRANGED"}:
        raise AppException("DATA_CONFLICT", "学生实习去向已落实")
    participant = db.scalar(select(InternshipBatchParticipant).where(
        InternshipBatchParticipant.tenant_id == tenant_id,
        InternshipBatchParticipant.batch_id == campaign.batch_id,
        InternshipBatchParticipant.student_id == record.student_id,
        InternshipBatchParticipant.status == "ACTIVE",
        InternshipBatchParticipant.is_deleted.is_(False),
    ))
    if not participant:
        raise AppException("NO_PERMISSION", "学生不在当前批次正式参与名单")
    if position.tenant_id != tenant_id or position.batch_id != campaign.batch_id or position.campaign_id != campaign.id:
        raise not_found("岗位不属于当前招聘季/批次")
    if position.status != "PUBLISHED" or int(position.allocated_count or 0) >= int(position.headcount or 0):
        raise AppException("DATA_CONFLICT", "岗位未发布、已下架或已满员")
    company = db.scalar(select(EmpCompany).where(EmpCompany.id == position.company_id, EmpCompany.tenant_id == tenant_id, EmpCompany.is_deleted.is_(False)))
    if not company or company.blacklist or company.coop_status != "ACTIVE":
        raise AppException("NO_PERMISSION", "岗位企业当前不可参与招聘")
    if company.access_valid_until and company.access_valid_until < (now or datetime.utcnow()):
        raise AppException("NO_PERMISSION", "企业准入已过期")
    accepted = db.scalar(select(InternshipCampaignEnterprise.id).where(
        InternshipCampaignEnterprise.tenant_id == tenant_id,
        InternshipCampaignEnterprise.campaign_id == campaign.id,
        InternshipCampaignEnterprise.company_id == company.id,
        InternshipCampaignEnterprise.status == "ACCEPTED",
        InternshipCampaignEnterprise.is_deleted.is_(False),
    ))
    if not accepted:
        raise AppException("NO_PERMISSION", "企业未接受当前招聘季邀请")
    student = db.scalar(select(StudentProfile).where(StudentProfile.id == record.student_id, StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False)))
    batch = db.scalar(select(InternshipBatch).where(InternshipBatch.id == campaign.batch_id, InternshipBatch.tenant_id == tenant_id, InternshipBatch.is_deleted.is_(False)))
    if not student or not batch:
        raise AppException("DATA_CONFLICT", "学生主档或实习批次不存在")
    rights = evaluate_position_publishability(position, company, batch, student, operation="APPLY", db=db)
    if not rights.get("passed"):
        raise AppException("DATA_CONFLICT", "岗位劳动权益/准入校验未通过", details={"blockers": rights.get("blockers", []), "unknowns": rights.get("unknowns", [])})
    return {"eligible": True, "position": position, "company": company, "rights": rights, "majorMatchHardBlock": False}
