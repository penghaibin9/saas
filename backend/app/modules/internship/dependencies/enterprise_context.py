"""Server-derived EnterpriseContext for the internship enterprise portal.

Client payloads never choose company scope. The signed enterprise member context is revalidated
against t_user/t_internship_enterprise_member on every request, then Grant/CampaignEnterprise
are resolved server-side for campaign operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Header
from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException, unauthorized
from app.db.session import get_sessionmaker
from app.models import EmpCompany
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise
from app.modules.internship.services import internship_enterprise_access_service as access_svc
from app.modules.internship.services import internship_enterprise_auth_service as auth_svc
from app.modules.internship.services.internship_recruitment_campaign_service import _get_campaign


@dataclass(frozen=True)
class EnterprisePrincipal:
    tenant_id: int
    tenant_code: str
    user_id: int
    member_id: int
    company_id: int
    member_role: str
    claims: dict


@dataclass(frozen=True)
class EnterpriseContext(EnterprisePrincipal):
    grant_id: int
    grant_type: str
    campaign_id: int | None = None
    batch_id: int | None = None


def _bearer(authorization: Optional[str]) -> str:
    value = str(authorization or "").strip()
    if value.startswith("Bearer "):
        value = value[7:].strip()
    if not value:
        raise unauthorized("未提供企业认证令牌")
    return value


def get_enterprise_principal(authorization: Optional[str] = Header(default=None)) -> EnterprisePrincipal:
    claims, tenant, user, member = auth_svc.decode_and_validate_access(_bearer(authorization))
    db = get_sessionmaker()()
    try:
        company = db.scalar(
            select(EmpCompany).where(
                EmpCompany.id == member.company_id,
                EmpCompany.tenant_id == tenant.id,
                EmpCompany.is_deleted.is_(False),
            )
        )
        if not company:
            raise AppException("NO_PERMISSION", "企业主档不存在或已移出当前学校")
        if (company.status or "").upper() != "ACTIVE":
            raise AppException("NO_PERMISSION", "企业主档已停用，协同访问被拒绝")
        if company.blacklist or company.coop_status == "BLACKLIST":
            raise AppException("NO_PERMISSION", "企业已进入黑名单，协同访问被拒绝")
        if company.coop_status != "ACTIVE" or company.qualification_status != "PASSED":
            raise AppException("NO_PERMISSION", "企业合作或资质状态已失效")
        if company.access_valid_until is not None and company.access_valid_until < datetime.utcnow():
            raise AppException("NO_PERMISSION", "企业准入有效期已过期")
    finally:
        db.close()

    principal = EnterprisePrincipal(
        tenant_id=int(tenant.id),
        tenant_code=str(tenant.tenant_code),
        user_id=int(user.id),
        member_id=int(member.id),
        company_id=int(member.company_id),
        member_role=str(member.member_role),
        claims=dict(claims),
    )
    # Downstream canonical internship services use the existing request context/_tid() path.
    # Populate it from signed/revalidated claims, never from a client companyId/body field.
    set_tenant({
        "tenantId": str(principal.tenant_id),
        "tenantCode": principal.tenant_code,
        "schoolName": str(claims.get("tenantName") or ""),
    })
    set_current_user({
        "userId": f"db-{principal.user_id}",
        "userType": "ENTERPRISE_MENTOR",
        "tenantId": str(principal.tenant_id),
        "tenantCode": principal.tenant_code,
        "enterpriseMemberId": str(principal.member_id),
        "companyId": str(principal.company_id),
        "memberRole": principal.member_role,
        "tokenJti": claims.get("jti"),
        "tokenExp": claims.get("exp"),
    })
    return principal


def resolve_recruitment_context(
    principal: EnterprisePrincipal,
    *,
    campaign_id: int,
) -> EnterpriseContext:
    db = get_sessionmaker()()
    try:
        campaign = _get_campaign(
            db,
            campaign_id,
            tenant_id=principal.tenant_id,
        )
        grant = access_svc.resolve_active_grant_in_tx(
            db,
            tenant_id=principal.tenant_id,
            member_id=principal.member_id,
            grant_type="RECRUITMENT",
            campaign_id=campaign.id,
            batch_id=campaign.batch_id,
        )
        participation = db.scalar(
            select(InternshipCampaignEnterprise).where(
                InternshipCampaignEnterprise.tenant_id == principal.tenant_id,
                InternshipCampaignEnterprise.campaign_id == campaign.id,
                InternshipCampaignEnterprise.company_id == principal.company_id,
                InternshipCampaignEnterprise.status == "ACCEPTED",
                InternshipCampaignEnterprise.is_deleted.is_(False),
            )
        )
        if not participation:
            raise AppException("NO_PERMISSION", "企业未接受当前招聘季或参与资格已撤销")
        return EnterpriseContext(
            **principal.__dict__,
            grant_id=int(grant.id),
            grant_type="RECRUITMENT",
            campaign_id=int(campaign.id),
            batch_id=int(campaign.batch_id),
        )
    finally:
        db.close()


def resolve_internship_collab_context(
    principal: EnterprisePrincipal,
    *,
    batch_id: int,
) -> EnterpriseContext:
    db = get_sessionmaker()()
    try:
        grant = access_svc.resolve_active_grant_in_tx(
            db,
            tenant_id=principal.tenant_id,
            member_id=principal.member_id,
            grant_type="INTERNSHIP_COLLAB",
            batch_id=batch_id,
        )
        return EnterpriseContext(
            **principal.__dict__,
            grant_id=int(grant.id),
            grant_type="INTERNSHIP_COLLAB",
            campaign_id=int(grant.campaign_id) if grant.campaign_id else None,
            batch_id=int(grant.batch_id) if grant.batch_id else None,
        )
    finally:
        db.close()


def assert_resource_company(context: EnterprisePrincipal, resource_company_id: int) -> None:
    if int(resource_company_id) != context.company_id:
        raise AppException("NO_PERMISSION", "资源不属于当前企业上下文")
