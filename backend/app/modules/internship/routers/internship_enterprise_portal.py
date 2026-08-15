"""Enterprise internship portal auth/context/applicant endpoints.

This router is registered without the staff internship dependency bundle. Protected endpoints
derive company scope only from signed/revalidated EnterpriseMember context.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.v1.file_contract import validated_local_file_response
from app.core.exceptions import AppException
from app.core.response import success
from app.modules.internship.dependencies.enterprise_context import (
    EnterprisePrincipal,
    require_enterprise_permission as require_permission,
    resolve_recruitment_context,
)
from app.modules.internship.schemas.internship_recruitment_campaign import (
    EnterpriseInviteAccept,
    EnterpriseInviteInspect,
    EnterpriseLogin,
    EnterpriseRefresh,
)
from app.modules.internship.services import internship_application_resume_pdf_service as resume_pdf_svc
from app.modules.internship.services import internship_enterprise_auth_service as auth_svc
from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc
from app.modules.internship.services import internship_enterprise_position_service as portal_svc
from app.modules.internship.services.internship_assignment_snapshot_authority import (
    install_assignment_snapshot_authority,
)
from app.services import audit_log
from app.services.db_service import session

install_assignment_snapshot_authority()

router = APIRouter(prefix="/internship/enterprise-portal", tags=["岗位实习-企业协同端"])


class EnterpriseDecisionBody(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=1000)
    interviewAt: str | None = None
    interviewNote: str | None = Field(default=None, max_length=1000)


class EnterpriseWithdrawAcceptBody(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class EnterpriseCompanyProfilePatch(BaseModel):
    expectedVersion: int = Field(ge=0)
    logoFileId: str | None = None
    shortName: str | None = Field(default=None, max_length=100)
    shortIntro: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=300)
    mainBusiness: str | None = Field(default=None, max_length=1000)
    establishedYear: int | None = None
    address: str | None = Field(default=None, max_length=300)


class EnterprisePositionDraftBody(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    headcount: int | None = None
    workLocation: str | None = Field(default=None, max_length=200)
    workAddress: str | None = Field(default=None, max_length=300)
    majorRequirement: str | None = Field(default=None, max_length=200)
    gradeRequirement: str | None = Field(default=None, max_length=100)
    mentorContactId: int | None = None
    workContent: str | None = None
    remark: str | None = Field(default=None, max_length=500)
    dailyHours: float | None = None
    weeklyHours: float | None = None
    shiftType: str | None = Field(default=None, max_length=30)
    nightShift: bool | None = None
    overtimeAllowed: bool | None = None
    restDaysPerWeek: float | None = None
    remunerationType: str | None = Field(default=None, max_length=30)
    remunerationAmount: float | None = None
    remunerationCycle: str | None = Field(default=None, max_length=30)
    salaryRange: str | None = Field(default=None, max_length=50)
    subsidy: str | None = Field(default=None, max_length=50)
    accommodationProvided: bool | None = None
    mealProvided: bool | None = None
    hazardousFlag: bool | None = None
    specialEquipment: str | None = Field(default=None, max_length=200)
    prohibitedReason: str | None = Field(default=None, max_length=500)


class EnterprisePositionUpdateBody(EnterprisePositionDraftBody):
    expectedVersion: int = Field(ge=0)


class EnterprisePositionTransitionBody(BaseModel):
    expectedVersion: int = Field(ge=0)


def _parse_datetime(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field} 必须是 ISO-8601 日期时间") from exc


@router.post("/auth/invite/inspect", openapi_extra={"x-internship-auth": "public"})
def inspect_invite(body: EnterpriseInviteInspect):
    return success(auth_svc.inspect_invite(tenant_code=body.tenantCode, token=body.token))


@router.post("/auth/invite/accept", openapi_extra={"x-internship-auth": "public"})
def accept_invite(body: EnterpriseInviteAccept):
    result = auth_svc.accept_invite(tenant_code=body.tenantCode, token=body.token, phone=body.phone, password=body.password)
    audit_log.record("ENTERPRISE_INVITE_ACCEPT", f"enterprise-member:{result['context']['memberId']}", detail={"companyId": result["context"]["companyId"]}, tenant_id=int(result["context"]["tenantId"]))
    return success(result, message="企业邀请已接受")


@router.post("/auth/login", openapi_extra={"x-internship-auth": "public"})
def login(body: EnterpriseLogin):
    result = auth_svc.login(tenant_code=body.tenantCode, login_name=body.loginName, password=body.password, member_id=body.memberId)
    audit_log.record("ENTERPRISE_LOGIN", f"enterprise-member:{result['context']['memberId']}", detail={"companyId": result["context"]["companyId"]}, tenant_id=int(result["context"]["tenantId"]))
    return success(result)


@router.post("/auth/refresh", openapi_extra={"x-internship-auth": "public"})
def refresh(body: EnterpriseRefresh):
    return success(auth_svc.refresh(refresh_token=body.refreshToken))


@router.get("/campaigns")
def campaigns(principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    with session() as db:
        return success(portal_svc.campaigns_for_principal_in_tx(db, principal=principal))


@router.get("/context")
def enterprise_context(campaignId: str = Query(..., description="当前招聘季；服务端据此校验 Grant/参与关系"), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=int(campaignId))
    with session() as db:
        return success(portal_svc.context_projection_in_tx(db, context=ctx))


@router.get("/dashboard")
def enterprise_dashboard(campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        return success(portal_svc.dashboard_in_tx(db, context=ctx))


@router.get("/company")
def company_profile(principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    with session() as db:
        return success(portal_svc.company_profile_in_tx(db, context=principal))


@router.put("/company")
def update_company_profile(body: EnterpriseCompanyProfilePatch, principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    with session() as db:
        result = portal_svc.update_company_profile_in_tx(db, context=principal, payload=body.model_dump(exclude_unset=True))
        db.commit()
        return success(result, message="企业公开资料已保存")


@router.get("/positions")
def enterprise_positions(campaignId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), status: str | None = Query(default=None), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        return success(portal_svc.list_positions_in_tx(db, context=ctx, page=page, page_size=pageSize, status=status))


@router.post("/positions")
def create_enterprise_position(body: EnterprisePositionDraftBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        result = portal_svc.create_position_in_tx(db, context=ctx, payload=body.model_dump(exclude_unset=True))
        db.commit()
        return success(result, message="岗位草稿已创建")


@router.get("/positions/{position_id}")
def enterprise_position_detail(position_id: int, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        return success(portal_svc.get_position_in_tx(db, context=ctx, position_id=position_id))


@router.put("/positions/{position_id}")
def update_enterprise_position(position_id: int, body: EnterprisePositionUpdateBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        result = portal_svc.update_position_in_tx(db, context=ctx, position_id=position_id, payload=body.model_dump(exclude_unset=True))
        db.commit()
        return success(result, message="岗位草稿已保存")


@router.post("/positions/{position_id}/submit")
def submit_enterprise_position(position_id: int, body: EnterprisePositionTransitionBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        result = portal_svc.submit_position_in_tx(db, context=ctx, position_id=position_id, expected_version=body.expectedVersion)
        db.commit()
        return success(result, message="岗位已提交学校审核")


@router.post("/positions/{position_id}/withdraw")
def withdraw_enterprise_position(position_id: int, body: EnterprisePositionTransitionBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.enterprise.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        result = portal_svc.withdraw_position_in_tx(db, context=ctx, position_id=position_id, expected_version=body.expectedVersion)
        db.commit()
        return success(result, message="岗位已撤回到草稿")


@router.get("/applications")
def applications(campaignId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), positionId: int | None = Query(default=None, ge=1), decisionStatus: str | None = Query(default=None), principal: EnterprisePrincipal = Depends(require_permission("internship.application.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        items, total = decision_svc.list_owned_applications_in_tx(db, context=ctx, page=page, page_size=pageSize, position_id=positionId, decision_status=decisionStatus)
        return success({"items": items, "total": total, "page": page, "pageSize": pageSize})


@router.get("/applications/{application_id}")
def application_detail(application_id: int, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.application.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        return success(decision_svc.material_detail_in_tx(db, context=ctx, application_id=application_id))


@router.get("/applications/{application_id}/resume-pdf", summary="企业按申请归属查看冻结实习档案 PDF")
def application_resume_pdf(application_id: int, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.application.view"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        file_row, snapshot = resume_pdf_svc.resolve_enterprise_resume_pdf_in_tx(
            db, context=ctx, application_id=application_id,
        )
        path = resume_pdf_svc.materialize_pdf_for_delivery(file_row)
        filename = file_row.file_name or f"internship-application-{application_id}.pdf"
        file_id = str(file_row.id)
        snapshot_id = str(snapshot.id)
        snapshot_hash = str(snapshot.snapshot_hash or "")
        submission_version = int(snapshot.submission_version or 0)
        db.commit()
    return validated_local_file_response(
        path,
        filename=filename,
        inline=True,
        media_type="application/pdf",
        audit_action="INTERNSHIP_ENTERPRISE_RESUME_PDF_VIEW",
        audit_target=f"internship-application:{application_id}",
        headers={"X-Internship-Snapshot-Hash": snapshot_hash},
        audit_detail={
            "applicationId": str(application_id),
            "campaignId": str(ctx.campaign_id),
            "companyId": str(ctx.company_id),
            "snapshotId": snapshot_id,
            "submissionVersion": submission_version,
            "fileId": file_id,
        },
    )


@router.post("/applications/{application_id}/contact-view")
def application_contact_view(application_id: int, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.application.review"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        result = decision_svc.contact_view_in_tx(db, context=ctx, application_id=application_id)
        db.commit()
        return success(result)


@router.post("/applications/{application_id}/decision")
def application_decision(application_id: int, body: EnterpriseDecisionBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.application.review"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    interview_at = _parse_datetime(body.interviewAt, "interviewAt")
    with session() as db:
        row = decision_svc.set_decision_in_tx(db, context=ctx, application_id=application_id, status=body.status, reason=body.reason, interview_at=interview_at, interview_note=body.interviewNote)
        db.commit()
        return success({"id": str(row.id), "applicationId": str(row.application_id), "decisionStatus": row.decision_status, "effectStatus": row.effect_status, "validUntil": row.valid_until.isoformat() if row.valid_until else None, "version": int(row.version or 0)})


@router.post("/applications/{application_id}/withdraw-accept")
def withdraw_accept(application_id: int, body: EnterpriseWithdrawAcceptBody, campaignId: int = Query(..., ge=1), principal: EnterprisePrincipal = Depends(require_permission("internship.application.review"))):
    ctx = resolve_recruitment_context(principal, campaign_id=campaignId)
    with session() as db:
        row = decision_svc.withdraw_accept_in_tx(db, context=ctx, application_id=application_id, reason=body.reason)
        db.commit()
        return success({"id": str(row.id), "applicationId": str(row.application_id), "decisionStatus": row.decision_status, "effectStatus": row.effect_status, "version": int(row.version or 0)}, message="拟接收已撤回")
