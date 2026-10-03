"""School-side RecruitmentCampaign API.

This router stays inside the existing staff internship bundle. Enterprise portal routes are
registered separately and never inherit require_staff.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_any_permission
from app.core.response import success
from app.modules.internship.schemas.internship_recruitment_campaign import (
    VolunteerLockRelease,
    VolunteerSchoolConfirm,
    CampaignEnterpriseInvite,
    CampaignEnterpriseRevoke,
    RecruitmentCampaignCreate,
    RecruitmentCampaignUpdate,
    RecruitmentCampaignVersionAction,
)
from app.modules.internship.services import internship_campaign_enterprise_service as enterprise_svc
from app.modules.internship.services import internship_enterprise_auth_service as enterprise_auth_svc
from app.modules.internship.services import internship_recruitment_campaign_service as campaign_svc
from app.modules.internship.services import internship_volunteer_group_service as group_svc
from app.modules.internship.services import internship_school_volunteer_service as school_volunteer_svc
from app.services import audit_log

router = APIRouter(prefix="/internship/recruitment-campaigns", tags=["岗位实习-招聘季"])

_VIEW = require_any_permission("internship.recruitment.view", "internship.enterprise.view")
_MANAGE = require_any_permission("internship.recruitment.manage", "internship.enterprise.manage")
_INVITE = require_any_permission("internship.recruitment.invite", "internship.enterprise.manage")
_CLOSE = require_any_permission("internship.recruitment.close", "internship.enterprise.manage")
_VOLUNTEER_REVIEW = require_any_permission("internship.application.review", "internship.recruitment.manage")
_VOLUNTEER_VIEW = require_any_permission("internship.application.view", "internship.recruitment.manage")


def _actor_id(user) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else None


@router.get("")
def list_campaigns(
    batchId: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    user=Depends(_VIEW),
):
    _ = user
    return success(campaign_svc.list_campaigns(batch_id=batchId, page=page, page_size=pageSize))


@router.post("")
def create_campaign(body: RecruitmentCampaignCreate, user=Depends(_MANAGE)):
    payload = body.model_dump()
    result = campaign_svc.create_campaign(payload, user=user)
    audit_log.record(
        "CREATE_RECRUITMENT_CAMPAIGN",
        f"internship-recruitment-campaign:{result['id']}",
        detail={"batchId": result["batchId"], "campaignCode": result["campaignCode"]},
    )
    return success(result, message="招聘季已创建")


@router.get("/review-context")
def volunteer_review_context(batchId: int = Query(..., ge=1), user=Depends(_VOLUNTEER_VIEW)):
    return success(school_volunteer_svc.review_context(batch_id=batchId, user=user))


@router.get("/{campaign_id}")
def campaign_detail(campaign_id: str, user=Depends(_VIEW)):
    _ = user
    return success(campaign_svc.get_campaign(campaign_id))


@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, body: RecruitmentCampaignUpdate, user=Depends(_MANAGE)):
    result = campaign_svc.update_campaign(
        campaign_id,
        body.model_dump(exclude_unset=True),
        user=user,
    )
    audit_log.record("UPDATE_RECRUITMENT_CAMPAIGN", f"internship-recruitment-campaign:{campaign_id}")
    return success(result, message="招聘季已更新")


def _transition(campaign_id: str, target: str, body: RecruitmentCampaignVersionAction, user):
    result = campaign_svc.transition_campaign(
        campaign_id,
        target,
        body.model_dump(),
        user=user,
    )
    audit_log.record(
        f"{target}_RECRUITMENT_CAMPAIGN",
        f"internship-recruitment-campaign:{campaign_id}",
        detail={"status": target},
    )
    return success(result, message=f"招聘季已{target}")


@router.post("/{campaign_id}/open")
def open_campaign(campaign_id: str, body: RecruitmentCampaignVersionAction, user=Depends(_MANAGE)):
    return _transition(campaign_id, "OPEN", body, user)


@router.post("/{campaign_id}/freeze")
def freeze_campaign(campaign_id: str, body: RecruitmentCampaignVersionAction, user=Depends(_MANAGE)):
    return _transition(campaign_id, "FROZEN", body, user)


@router.post("/{campaign_id}/close")
def close_campaign(campaign_id: str, body: RecruitmentCampaignVersionAction, user=Depends(_CLOSE)):
    return _transition(campaign_id, "CLOSED", body, user)


@router.post("/{campaign_id}/archive")
def archive_campaign(campaign_id: str, body: RecruitmentCampaignVersionAction, user=Depends(_CLOSE)):
    return _transition(campaign_id, "ARCHIVED", body, user)


@router.get("/{campaign_id}/enterprises")
def list_campaign_enterprises(
    campaign_id: str,
    status: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    user=Depends(_VIEW),
):
    _ = user
    return success(
        enterprise_svc.list_campaign_enterprises(
            campaign_id,
            status=status,
            page=page,
            page_size=pageSize,
        )
    )


@router.post("/{campaign_id}/enterprises/invite")
def invite_company(campaign_id: str, body: CampaignEnterpriseInvite, user=Depends(_INVITE)):
    result = enterprise_auth_svc.issue_company_invite(
        campaign_id,
        company_id=body.companyId,
        login_name=body.loginName,
        real_name=body.realName,
        phone=body.phone,
        member_role=body.memberRole,
        invite_source=body.inviteSource,
        actor_user_id=_actor_id(user),
    )
    audit_log.record(
        "INVITE_RECRUITMENT_ENTERPRISE",
        f"internship-recruitment-campaign:{campaign_id}:company:{body.companyId}",
        detail={"memberId": result["memberId"], "inviteSource": body.inviteSource},
    )
    # inviteToken is intentionally returned only on this authenticated school write; DB stores hash only.
    return success(result, message="企业邀请已生成")


@router.post("/{campaign_id}/enterprises/{company_id}/revoke")
def revoke_company(
    campaign_id: str,
    company_id: str,
    body: CampaignEnterpriseRevoke,
    user=Depends(_INVITE),
):
    result = enterprise_svc.transition_participation(
        campaign_id,
        company_id,
        "REVOKED",
        {"expectedVersion": body.expectedVersion, "reason": body.reason},
    )
    audit_log.record(
        "REVOKE_RECRUITMENT_ENTERPRISE",
        f"internship-recruitment-campaign:{campaign_id}:company:{company_id}",
        detail={"reason": body.reason},
    )
    return success(result, message="企业招聘季参与资格已撤销")


@router.get("/{campaign_id}/volunteer-groups")
def school_volunteer_groups(
    campaign_id: int,
    status: str = "PENDING",
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(_VOLUNTEER_VIEW),
):
    return success(school_volunteer_svc.list_groups(
        campaign_id=campaign_id, user=user, status=status, keyword=keyword,
        page=page, page_size=pageSize,
    ))


@router.get("/{campaign_id}/volunteer-groups/{group_id}")
def school_volunteer_detail(campaign_id: int, group_id: int, user=Depends(_VOLUNTEER_VIEW)):
    return success(school_volunteer_svc.get_group(campaign_id=campaign_id, group_id=group_id, user=user))


@router.post("/{campaign_id}/volunteer-groups/{group_id}/confirm")
def confirm_school_volunteer(campaign_id: int, group_id: int, body: VolunteerSchoolConfirm,
                             user=Depends(_VOLUNTEER_REVIEW)):
    return success(school_volunteer_svc.confirm_group(
        campaign_id=campaign_id, group_id=group_id, application_id=body.applicationId, user=user,
        expected_group_version=body.expectedGroupVersion, expected_record_version=body.expectedRecordVersion,
        expected_application_version=body.expectedApplicationVersion,
    ), message="岗位已确认，协议、保险与上岗条件需继续核验")


@router.post("/{campaign_id}/volunteer-groups/{group_id}/return")
@router.post("/{campaign_id}/volunteer-groups/{group_id}/release")
def release_volunteer_lock(
    campaign_id: int,
    group_id: int,
    body: VolunteerLockRelease,
    user=Depends(_VOLUNTEER_REVIEW),
):
    result = group_svc.teacher_release_group_lock(
        group_id=group_id,
        campaign_id=campaign_id,
        reason=body.reason,
        user=user,
        expected_group_version=body.expectedGroupVersion,
        expected_record_version=body.expectedRecordVersion,
    )
    audit_log.record(
        "RELEASE_VOLUNTEER_ENTERPRISE_CONFIRM_LOCK",
        f"internship-volunteer-group:{group_id}",
        detail={"campaignId": str(campaign_id), "reason": body.reason},
    )
    return success(result, message="志愿已退回，学生可修改后重新提交")
