"""EnterpriseAccessGrant authority service for E-A01.

A grant never replaces enterprise membership. Effective access requires an ACTIVE member and
an ACTIVE, in-window grant. RECRUITMENT grants additionally bind an ACCEPTED campaign-company
participation; INTERNSHIP_COLLAB grants bind the formal internship batch.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import InternshipBatch
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise,
    InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember,
)
from app.modules.internship.enterprise_collaboration_contract import ENTERPRISE_GRANT_TYPES
from app.modules.internship.services.internship_enterprise_member_service import _get_member
from app.modules.internship.services.internship_recruitment_campaign_service import _get_campaign
from app.services.db_service import _as_id, _iso, _tid, session


def effective_grant_status(
    grant: InternshipEnterpriseAccessGrant,
    *,
    now: datetime | None = None,
) -> str:
    status = (grant.status or "ACTIVE").upper()
    if status in {"REVOKED", "EXPIRED"}:
        return status
    current = now or datetime.utcnow()
    if current < grant.valid_from:
        return "NOT_STARTED"
    if current > grant.valid_until:
        return "EXPIRED"
    return "ACTIVE"


def _scope_predicates(*, grant_type: str, campaign_id: int | None, batch_id: int | None):
    predicates = [InternshipEnterpriseAccessGrant.grant_type == grant_type]
    predicates.append(
        InternshipEnterpriseAccessGrant.campaign_id.is_(None)
        if campaign_id is None
        else InternshipEnterpriseAccessGrant.campaign_id == campaign_id
    )
    predicates.append(
        InternshipEnterpriseAccessGrant.batch_id.is_(None)
        if batch_id is None
        else InternshipEnterpriseAccessGrant.batch_id == batch_id
    )
    return predicates


def _validate_scope_in_tx(
    db,
    *,
    member: InternshipEnterpriseMember,
    grant_type: str,
    campaign_id: int | None,
    batch_id: int | None,
    valid_until: datetime,
):
    tenant_id = member.tenant_id
    if grant_type == "RECRUITMENT":
        if campaign_id is None:
            raise AppException("VALIDATION_ERROR", "RECRUITMENT Grant 必须绑定 campaignId")
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        if campaign.status in {"CLOSED", "ARCHIVED"}:
            raise AppException("DATA_CONFLICT", "招聘季已关闭，不能发放 RECRUITMENT Grant")
        if batch_id is None:
            batch_id = campaign.batch_id
        if _as_id(batch_id) != campaign.batch_id:
            raise AppException("VALIDATION_ERROR", "Grant batchId 与招聘季批次不一致")
        if campaign.enterprise_access_end_at is None:
            raise AppException("DATA_CONFLICT", "招聘季未配置 enterpriseAccessEndAt")
        if valid_until > campaign.enterprise_access_end_at:
            raise AppException("VALIDATION_ERROR", "RECRUITMENT Grant 不得超过招聘季企业访问截止时间")
        participation = db.scalar(
            select(InternshipCampaignEnterprise).where(
                InternshipCampaignEnterprise.tenant_id == tenant_id,
                InternshipCampaignEnterprise.campaign_id == campaign.id,
                InternshipCampaignEnterprise.company_id == member.company_id,
                InternshipCampaignEnterprise.status == "ACCEPTED",
                InternshipCampaignEnterprise.is_deleted.is_(False),
            )
        )
        if not participation:
            raise AppException("NO_PERMISSION", "企业尚未 ACCEPTED 当前招聘季")
        return campaign.id, campaign.batch_id

    if batch_id is None:
        raise AppException("VALIDATION_ERROR", "INTERNSHIP_COLLAB Grant 必须绑定 batchId")
    batch = db.scalar(
        select(InternshipBatch).where(
            InternshipBatch.id == _as_id(batch_id),
            InternshipBatch.tenant_id == tenant_id,
            InternshipBatch.is_deleted.is_(False),
        )
    )
    if not batch:
        raise not_found("实习批次不存在或不在当前租户")
    if campaign_id is not None:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id)
        if campaign.batch_id != batch.id:
            raise AppException("VALIDATION_ERROR", "campaignId 与 batchId 不属于同一实习批次")
    return _as_id(campaign_id) if campaign_id is not None else None, batch.id


def issue_grant_in_tx(
    db,
    *,
    member_id: int,
    grant_type: str,
    valid_from: datetime,
    valid_until: datetime,
    campaign_id: int | None = None,
    batch_id: int | None = None,
    tenant_id: int | None = None,
) -> InternshipEnterpriseAccessGrant:
    """Issue/reuse a grant without committing, so invite activation can share one transaction.

    The member row is locked first. This also serializes duplicate issue attempts for scopes whose
    nullable campaign/batch columns cannot be fully protected by a MySQL UNIQUE with NULL values.
    """
    scope_tenant_id = int(tenant_id) if tenant_id is not None else _tid()
    kind = (grant_type or "").upper()
    if kind not in ENTERPRISE_GRANT_TYPES:
        raise AppException("VALIDATION_ERROR", "grantType 必须是 RECRUITMENT/INTERNSHIP_COLLAB")
    if not isinstance(valid_from, datetime) or not isinstance(valid_until, datetime):
        raise AppException("VALIDATION_ERROR", "validFrom/validUntil 必须是 datetime")
    if valid_from >= valid_until:
        raise AppException("VALIDATION_ERROR", "validFrom 必须早于 validUntil")

    member = _get_member(db, member_id, tenant_id=scope_tenant_id, lock=True)
    if member.status != "ACTIVE":
        raise AppException("NO_PERMISSION", "只有 ACTIVE 企业成员可以获得访问授权")

    campaign_id, batch_id = _validate_scope_in_tx(
        db,
        member=member,
        grant_type=kind,
        campaign_id=_as_id(campaign_id) if campaign_id is not None else None,
        batch_id=_as_id(batch_id) if batch_id is not None else None,
        valid_until=valid_until,
    )
    existing = db.scalar(
        select(InternshipEnterpriseAccessGrant).where(
            InternshipEnterpriseAccessGrant.tenant_id == scope_tenant_id,
            InternshipEnterpriseAccessGrant.member_id == member.id,
            InternshipEnterpriseAccessGrant.is_deleted.is_(False),
            *_scope_predicates(
                grant_type=kind,
                campaign_id=campaign_id,
                batch_id=batch_id,
            ),
        ).with_for_update()
    )
    if existing:
        if effective_grant_status(existing) == "ACTIVE":
            return existing
        raise AppException("DATA_CONFLICT", "该授权范围已有历史 Grant，不可静默覆盖或复活")

    grant = InternshipEnterpriseAccessGrant(
        tenant_id=scope_tenant_id,
        member_id=member.id,
        company_id=member.company_id,
        grant_type=kind,
        campaign_id=campaign_id,
        batch_id=batch_id,
        valid_from=valid_from,
        valid_until=valid_until,
        status="ACTIVE",
    )
    db.add(grant)
    db.flush()
    return grant


def issue_grant(**kwargs):
    with session() as db:
        grant = issue_grant_in_tx(db, **kwargs)
        db.commit()
        return _row(grant)


def _get_grant(db, grant_id: int, *, tenant_id: int, lock: bool = False):
    stmt = select(InternshipEnterpriseAccessGrant).where(
        InternshipEnterpriseAccessGrant.id == _as_id(grant_id),
        InternshipEnterpriseAccessGrant.tenant_id == tenant_id,
        InternshipEnterpriseAccessGrant.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    grant = db.scalar(stmt)
    if not grant:
        raise not_found("企业访问授权不存在或不在当前租户")
    return grant


def resolve_active_grant_in_tx(
    db,
    *,
    member_id: int,
    grant_type: str,
    campaign_id: int | None = None,
    batch_id: int | None = None,
    now: datetime | None = None,
    tenant_id: int | None = None,
) -> InternshipEnterpriseAccessGrant:
    scope_tenant_id = int(tenant_id) if tenant_id is not None else _tid()
    kind = (grant_type or "").upper()
    if kind not in ENTERPRISE_GRANT_TYPES:
        raise AppException("VALIDATION_ERROR", "grantType 非法")
    member = _get_member(db, member_id, tenant_id=scope_tenant_id)
    if member.status != "ACTIVE":
        raise AppException("NO_PERMISSION", "企业成员已停用")
    grant = db.scalar(
        select(InternshipEnterpriseAccessGrant).where(
            InternshipEnterpriseAccessGrant.tenant_id == scope_tenant_id,
            InternshipEnterpriseAccessGrant.member_id == member.id,
            InternshipEnterpriseAccessGrant.company_id == member.company_id,
            InternshipEnterpriseAccessGrant.is_deleted.is_(False),
            *_scope_predicates(
                grant_type=kind,
                campaign_id=_as_id(campaign_id) if campaign_id is not None else None,
                batch_id=_as_id(batch_id) if batch_id is not None else None,
            ),
        )
    )
    if not grant or effective_grant_status(grant, now=now) != "ACTIVE":
        raise AppException("NO_PERMISSION", "企业访问授权不存在、已撤销、未生效或已过期")
    return grant


def resolve_active_grant(**kwargs):
    with session() as db:
        return _row(resolve_active_grant_in_tx(db, **kwargs))


def revoke_grant(
    grant_id: int,
    *,
    expected_version: int,
    reason: str,
    revoked_by_user_id: int | None = None,
):
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "撤销授权必须填写原因")
    tenant_id = _tid()
    with session() as db:
        grant = _get_grant(db, grant_id, tenant_id=tenant_id, lock=True)
        current = int(grant.version or 0)
        if int(expected_version) != current:
            raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")
        if grant.status == "REVOKED":
            return _row(grant)
        if effective_grant_status(grant) == "EXPIRED":
            grant.status = "EXPIRED"
        else:
            grant.status = "REVOKED"
            grant.revoked_at = datetime.utcnow()
            grant.revoked_by_user_id = _as_id(revoked_by_user_id) if revoked_by_user_id is not None else None
            grant.revoke_reason = reason
        grant.version = current + 1
        db.commit()
        return _row(grant)


def _row(grant: InternshipEnterpriseAccessGrant):
    return {
        "id": str(grant.id),
        "memberId": str(grant.member_id),
        "companyId": str(grant.company_id),
        "grantType": grant.grant_type,
        "campaignId": str(grant.campaign_id) if grant.campaign_id else "",
        "batchId": str(grant.batch_id) if grant.batch_id else "",
        "validFrom": _iso(grant.valid_from),
        "validUntil": _iso(grant.valid_until),
        "status": grant.status,
        "effectiveStatus": effective_grant_status(grant),
        "revokedAt": _iso(grant.revoked_at),
        "revokeReason": grant.revoke_reason or "",
        "version": int(grant.version or 0),
    }
