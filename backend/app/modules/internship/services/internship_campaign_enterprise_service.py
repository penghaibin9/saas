"""CampaignEnterprise participation authority.

This service answers only whether an existing canonical EmpCompany participates in one
RecruitmentCampaign. Qualification, blacklist, cooperation state and admission validity stay
on EmpCompany and are re-checked on every participation write.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import EmpCompany
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise
from app.modules.internship.enterprise_collaboration_contract import (
    CAMPAIGN_ENTERPRISE_INVITE_SOURCES,
    CAMPAIGN_ENTERPRISE_TRANSITIONS,
)
from app.modules.internship.services.internship_recruitment_campaign_service import _get_campaign
from app.services.db_service import _as_id, _iso, _tid, session


def _actor_user_id(user) -> int | None:
    raw = (user or {}).get("id") or (user or {}).get("userId")
    try:
        return int(str(raw).removeprefix("db-")) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _get_company(db, company_id: int, *, tenant_id: int, require_admission: bool = False):
    company = db.scalar(
        select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id),
            EmpCompany.tenant_id == tenant_id,
            EmpCompany.is_deleted.is_(False),
        )
    )
    if not company:
        raise not_found("企业不存在或不在当前租户范围内")
    if require_admission:
        if (company.status or "").upper() != "ACTIVE":
            raise AppException("DATA_CONFLICT", "企业主档已停用")
        if company.blacklist or company.coop_status == "BLACKLIST":
            raise AppException("DATA_CONFLICT", "黑名单企业不能参加招聘季")
        if company.coop_status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "企业合作状态不是 ACTIVE")
        if company.qualification_status != "PASSED":
            raise AppException("DATA_CONFLICT", "企业资质尚未通过")
        if company.access_valid_until and company.access_valid_until < datetime.utcnow():
            raise AppException("DATA_CONFLICT", "企业准入已过期")
    return company


def _get_participation(
    db,
    *,
    tenant_id: int,
    campaign_id: int,
    company_id: int,
    lock: bool = False,
):
    stmt = select(InternshipCampaignEnterprise).where(
        InternshipCampaignEnterprise.tenant_id == tenant_id,
        InternshipCampaignEnterprise.campaign_id == _as_id(campaign_id),
        InternshipCampaignEnterprise.company_id == _as_id(company_id),
        InternshipCampaignEnterprise.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if not row:
        raise not_found("企业未加入该招聘季")
    return row


def _expected_version(row: InternshipCampaignEnterprise, body: dict) -> int:
    raw = body.get("expectedVersion", body.get("version"))
    if raw is None:
        raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（乐观锁）")
    try:
        expected = int(raw)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from exc
    current = int(row.version or 0)
    if expected != current:
        raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")
    return current


def _row(item: InternshipCampaignEnterprise, company: EmpCompany | None = None):
    return {
        "id": str(item.id),
        "campaignId": str(item.campaign_id),
        "companyId": str(item.company_id),
        "companyName": company.name if company else "",
        "status": item.status,
        "inviteSource": item.invite_source,
        "invitedByUserId": str(item.invited_by_user_id) if item.invited_by_user_id else "",
        "invitedAt": _iso(item.invited_at),
        "acceptedAt": _iso(item.accepted_at),
        "declinedAt": _iso(item.declined_at),
        "revokedAt": _iso(item.revoked_at),
        "revokeReason": item.revoke_reason or "",
        "version": int(item.version or 0),
    }


def invite_company(
    campaign_id: int,
    company_id: int,
    *,
    invite_source: str = "MANUAL",
    user=None,
):
    source = (invite_source or "MANUAL").upper()
    if source not in CAMPAIGN_ENTERPRISE_INVITE_SOURCES:
        raise AppException("VALIDATION_ERROR", "inviteSource 非法")
    tenant_id = _tid()
    with session() as db:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        if campaign.status not in {"DRAFT", "OPEN"}:
            raise AppException("DATA_CONFLICT", "当前招聘季已停止新增企业邀请")
        company = _get_company(db, company_id, tenant_id=tenant_id, require_admission=True)
        existing = db.scalar(
            select(InternshipCampaignEnterprise).where(
                InternshipCampaignEnterprise.tenant_id == tenant_id,
                InternshipCampaignEnterprise.campaign_id == campaign.id,
                InternshipCampaignEnterprise.company_id == company.id,
                InternshipCampaignEnterprise.is_deleted.is_(False),
            ).with_for_update()
        )
        if existing:
            if existing.status in {"INVITED", "ACCEPTED", "SUSPENDED"}:
                return _row(existing, company)
            raise AppException("DATA_CONFLICT", "该企业在本招聘季已有终态参与记录，不可静默重置")

        item = InternshipCampaignEnterprise(
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            company_id=company.id,
            status="INVITED",
            invite_source=source,
            invited_by_user_id=_actor_user_id(user),
            invited_at=datetime.utcnow(),
        )
        db.add(item)
        db.flush()
        db.commit()
        return _row(item, company)


def transition_participation(
    campaign_id: int,
    company_id: int,
    target_status: str,
    body: dict | None,
):
    body = dict(body or {})
    target = (target_status or "").upper()
    tenant_id = _tid()
    with session() as db:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        if campaign.status in {"CLOSED", "ARCHIVED"}:
            raise AppException("DATA_CONFLICT", "招聘季已关闭，只允许历史只读")
        item = _get_participation(
            db,
            tenant_id=tenant_id,
            campaign_id=campaign.id,
            company_id=company_id,
            lock=True,
        )
        current_version = _expected_version(item, body)
        allowed = CAMPAIGN_ENTERPRISE_TRANSITIONS.get(item.status, frozenset())
        if target not in allowed:
            raise AppException("DATA_CONFLICT", f"参与状态 {item.status} 不可迁移到 {target}")
        company = _get_company(
            db,
            company_id,
            tenant_id=tenant_id,
            require_admission=target == "ACCEPTED",
        )
        now = datetime.utcnow()
        if target == "ACCEPTED":
            item.accepted_at = now
        elif target == "DECLINED":
            item.declined_at = now
        elif target == "REVOKED":
            reason = (body.get("reason") or body.get("revokeReason") or "").strip()
            if len(reason) < 2:
                raise AppException("VALIDATION_ERROR", "REVOKED 必须填写撤销原因")
            item.revoked_at = now
            item.revoke_reason = reason
        item.status = target
        item.version = current_version + 1
        db.commit()
        return _row(item, company)


def list_campaign_enterprises(
    campaign_id: int,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    tenant_id = _tid()
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    with session() as db:
        _get_campaign(db, campaign_id, tenant_id=tenant_id)
        stmt = (
            select(InternshipCampaignEnterprise, EmpCompany)
            .join(
                EmpCompany,
                (EmpCompany.id == InternshipCampaignEnterprise.company_id)
                & (EmpCompany.tenant_id == InternshipCampaignEnterprise.tenant_id)
                & (EmpCompany.is_deleted.is_(False)),
            )
            .where(
                InternshipCampaignEnterprise.tenant_id == tenant_id,
                InternshipCampaignEnterprise.campaign_id == _as_id(campaign_id),
                InternshipCampaignEnterprise.is_deleted.is_(False),
            )
        )
        if status:
            stmt = stmt.where(InternshipCampaignEnterprise.status == status.upper())
        rows = db.execute(
            stmt.order_by(InternshipCampaignEnterprise.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).all()
        return {
            "items": [_row(item, company) for item, company in rows[:page_size]],
            "page": page,
            "pageSize": page_size,
            "hasMore": len(rows) > page_size,
        }
