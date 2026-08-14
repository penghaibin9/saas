"""Enterprise internship portal auth/context endpoints.

This router must be registered without the staff internship dependency bundle. Every protected
endpoint derives company scope from the signed/revalidated EnterpriseMember context.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.response import success
from app.modules.internship.dependencies.enterprise_context import (
    EnterprisePrincipal,
    get_enterprise_principal,
    resolve_recruitment_context,
)
from app.modules.internship.schemas.internship_recruitment_campaign import (
    EnterpriseInviteAccept,
    EnterpriseInviteInspect,
    EnterpriseLogin,
    EnterpriseRefresh,
)
from app.modules.internship.services import internship_enterprise_auth_service as auth_svc
from app.services import audit_log

router = APIRouter(prefix="/internship/enterprise-portal", tags=["岗位实习-企业协同端"])


@router.post("/auth/invite/inspect")
def inspect_invite(body: EnterpriseInviteInspect):
    return success(auth_svc.inspect_invite(tenant_code=body.tenantCode, token=body.token))


@router.post("/auth/invite/accept")
def accept_invite(body: EnterpriseInviteAccept):
    result = auth_svc.accept_invite(
        tenant_code=body.tenantCode,
        token=body.token,
        phone=body.phone,
        password=body.password,
    )
    audit_log.record(
        "ENTERPRISE_INVITE_ACCEPT",
        f"enterprise-member:{result['context']['memberId']}",
        detail={"companyId": result["context"]["companyId"]},
        tenant_id=int(result["context"]["tenantId"]),
    )
    return success(result, message="企业邀请已接受")


@router.post("/auth/login")
def login(body: EnterpriseLogin):
    result = auth_svc.login(
        tenant_code=body.tenantCode,
        login_name=body.loginName,
        password=body.password,
        member_id=body.memberId,
    )
    audit_log.record(
        "ENTERPRISE_LOGIN",
        f"enterprise-member:{result['context']['memberId']}",
        detail={"companyId": result["context"]["companyId"]},
        tenant_id=int(result["context"]["tenantId"]),
    )
    return success(result)


@router.post("/auth/refresh")
def refresh(body: EnterpriseRefresh):
    return success(auth_svc.refresh(refresh_token=body.refreshToken))


@router.get("/context")
def enterprise_context(
    campaignId: str = Query(..., description="当前招聘季；服务端据此校验 Grant/参与关系"),
    principal: EnterprisePrincipal = Depends(get_enterprise_principal),
):
    ctx = resolve_recruitment_context(principal, campaign_id=int(campaignId))
    return success({
        "tenantId": str(ctx.tenant_id),
        "tenantCode": ctx.tenant_code,
        "memberId": str(ctx.member_id),
        "memberRole": ctx.member_role,
        "companyId": str(ctx.company_id),
        "campaignId": str(ctx.campaign_id),
        "batchId": str(ctx.batch_id),
        "grantId": str(ctx.grant_id),
        "grantType": ctx.grant_type,
    })
