"""E-A01 enterprise invite activation and login facade.

Cryptography/auth primitives are reused from the platform: PBKDF2 password hashing,
JWT access-token creation/verification and shared refresh-token storage. Invite secrets are
single-use random values; only the platform HMAC digest is persisted.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, unauthorized
from app.core.field_crypto import (
    decrypt_sensitive,
    encrypt_sensitive,
    hash_sensitive,
    mask_phone,
)
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.core.token_store import consume_refresh, issue_refresh, jti_blocked
from app.db.session import get_sessionmaker
from app.models import EmpCompany, Tenant, User
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise,
    InternshipEnterpriseMember,
)
from app.modules.internship.services import internship_enterprise_access_service as access_svc
from app.modules.internship.services import internship_recruitment_window_guard as window_guard
from app.modules.internship.services.internship_campaign_enterprise_service import _get_company
from app.modules.internship.services.internship_recruitment_campaign_service import _get_campaign
from app.services.db_service import _as_id, _tid

_INVITE_PREFIX = "ei"
_INVITE_TTL = timedelta(days=7)


def _now() -> datetime:
    from app.core.timeutil import utc_now_naive
    return utc_now_naive()


def _invite_hash(token: str) -> str:
    digest = hash_sensitive(token, "internship_enterprise_invite")
    if not digest:
        raise AppException("VALIDATION_ERROR", "邀请 token 不能为空")
    return digest


def _parse_invite_token(token: str) -> tuple[int, int]:
    parts = str(token or "").split(".")
    if len(parts) != 4 or parts[0] != _INVITE_PREFIX:
        raise AppException("UNAUTHORIZED", "邀请链接无效或已失效", http_status=401)
    try:
        campaign_id = int(parts[1])
        member_id = int(parts[2])
    except (TypeError, ValueError) as exc:
        raise AppException("UNAUTHORIZED", "邀请链接无效或已失效", http_status=401) from exc
    if campaign_id <= 0 or member_id <= 0 or len(parts[3]) < 32:
        raise AppException("UNAUTHORIZED", "邀请链接无效或已失效", http_status=401)
    return campaign_id, member_id


def _tenant_by_code(db, tenant_code: str):
    code = str(tenant_code or "").strip()
    tenant = db.scalar(
        select(Tenant).where(
            Tenant.tenant_code == code,
            Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
            Tenant.is_deleted.is_(False),
        )
    )
    if not tenant:
        raise unauthorized("学校编码、账号或邀请链接无效")
    return tenant


def _require_company_admission_for_auth(db, *, tenant_id: int, company_id: int):
    """Fail closed before issuing or renewing enterprise auth credentials.

    Business endpoints independently revalidate company admission as defense in depth. Auth
    must also reject a disabled/blacklisted/unqualified/expired company so login/refresh never
    succeeds only to fail on the first protected request.
    """
    try:
        return _get_company(
            db,
            company_id,
            tenant_id=tenant_id,
            require_admission=True,
        )
    except AppException as exc:
        raise AppException(
            "NO_PERMISSION",
            "企业准入状态已失效，请联系学校管理员",
            http_status=403,
        ) from exc


def _assert_invite_window(campaign, now: datetime, *, public_token: bool = False) -> None:
    try:
        window_guard.assert_campaign_operation_window(campaign, "INVITE", now=now)
        if campaign.enterprise_access_end_at is None or campaign.enterprise_access_end_at <= now:
            raise AppException("DATA_CONFLICT", "招聘季未配置有效企业访问截止时间")
    except AppException as exc:
        if public_token:
            raise unauthorized("邀请链接当前不可用或已失效") from exc
        raise


def _invite_expiry(campaign, now: datetime) -> datetime:
    _assert_invite_window(campaign, now)
    expiry = min(now + _INVITE_TTL, campaign.invite_end_at, campaign.enterprise_access_end_at)
    if expiry <= now:
        raise AppException("DATA_CONFLICT", "招聘季邀请窗口或企业访问期已结束")
    return expiry


def _ensure_campaign_invitation_in_tx(db, *, campaign, company, invite_source: str, actor_user_id: int | None):
    item = db.scalar(
        select(InternshipCampaignEnterprise).where(
            InternshipCampaignEnterprise.tenant_id == campaign.tenant_id,
            InternshipCampaignEnterprise.campaign_id == campaign.id,
            InternshipCampaignEnterprise.company_id == company.id,
            InternshipCampaignEnterprise.is_deleted.is_(False),
        ).with_for_update()
    )
    if item:
        if item.status == "INVITED":
            return item
        if item.status == "ACCEPTED":
            raise AppException("DATA_CONFLICT", "该企业已经接受当前招聘季邀请")
        raise AppException("DATA_CONFLICT", "该企业在当前招聘季已有终态/暂停记录，不可覆盖")
    item = InternshipCampaignEnterprise(
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        company_id=company.id,
        status="INVITED",
        invite_source=invite_source,
        invited_by_user_id=actor_user_id,
        invited_at=_now(),
    )
    db.add(item)
    db.flush()
    return item


def _ensure_invited_user_in_tx(
    db,
    *,
    tenant_id: int,
    login_name: str,
    real_name: str,
    phone: str,
):
    login = str(login_name or "").strip()
    display = str(real_name or "").strip()
    phone_text = str(phone or "").strip()
    if not login or not display or len(phone_text) < 6:
        raise AppException("VALIDATION_ERROR", "邀请联系人登录名、姓名、手机号不能为空")
    user = db.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.login_name == login,
            User.is_deleted.is_(False),
        ).with_for_update()
    )
    phone_hash = hash_sensitive(phone_text, "phone")
    if user:
        if (user.user_type or "").upper() != "ENTERPRISE_MENTOR":
            raise AppException("DATA_CONFLICT", "该登录账号已属于学校内部身份，不能绑定企业成员")
        if user.phone_hash and phone_hash and user.phone_hash != phone_hash:
            raise AppException("DATA_CONFLICT", "现有企业账号手机号与本次邀请不一致")
        return user

    # Frozen Member.user_id is non-null. Pre-provision a DISABLED t_user with an unguessable
    # password so the invite can own a Member/token before activation without a second auth DB.
    user = User(
        tenant_id=tenant_id,
        login_name=login,
        real_name=display,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        user_type="ENTERPRISE_MENTOR",
        phone_encrypted=encrypt_sensitive(phone_text, "phone"),
        phone_hash=phone_hash,
        status="DISABLED",
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    return user


def issue_company_invite(
    campaign_id: int,
    *,
    company_id: int,
    login_name: str,
    real_name: str,
    phone: str,
    member_role: str = "COMPANY_ADMIN",
    invite_source: str = "MANUAL",
    actor_user_id: int | None = None,
):
    tenant_id = _tid()
    role = (member_role or "").upper()
    if role not in {"COMPANY_ADMIN", "HR", "MENTOR"}:
        raise AppException("VALIDATION_ERROR", "memberRole 非法")
    source = (invite_source or "MANUAL").upper()
    if source not in {"MANUAL", "REUSE", "PUBLIC_REQUEST"}:
        raise AppException("VALIDATION_ERROR", "inviteSource 非法")

    db = get_sessionmaker()()
    try:
        campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=True)
        now = _now()
        expires_at = _invite_expiry(campaign, now)
        company = _get_company(db, company_id, tenant_id=tenant_id, require_admission=True)
        _ensure_campaign_invitation_in_tx(
            db,
            campaign=campaign,
            company=company,
            invite_source=source,
            actor_user_id=actor_user_id,
        )
        user = _ensure_invited_user_in_tx(
            db,
            tenant_id=tenant_id,
            login_name=login_name,
            real_name=real_name,
            phone=phone,
        )
        member = db.scalar(
            select(InternshipEnterpriseMember).where(
                InternshipEnterpriseMember.tenant_id == tenant_id,
                InternshipEnterpriseMember.company_id == company.id,
                InternshipEnterpriseMember.user_id == user.id,
                InternshipEnterpriseMember.is_deleted.is_(False),
            ).with_for_update()
        )
        if member and member.status == "DISABLED":
            raise AppException("NO_PERMISSION", "企业成员已被学校停用，不能重新发放邀请")
        if not member:
            member = InternshipEnterpriseMember(
                tenant_id=tenant_id,
                company_id=company.id,
                user_id=user.id,
                member_role=role,
                status="INVITED",
                is_primary=role == "COMPANY_ADMIN",
                invited_at=now,
            )
            db.add(member)
            db.flush()
        elif member.status == "ACTIVE":
            raise AppException("DATA_CONFLICT", "该联系人已是 ACTIVE 企业成员，请使用企业登录处理新招聘季")

        raw = f"{_INVITE_PREFIX}.{campaign.id}.{member.id}.{secrets.token_urlsafe(32)}"
        member.member_role = role
        member.invited_phone_hash = hash_sensitive(str(phone or "").strip(), "phone")
        member.invite_token_hash = _invite_hash(raw)
        member.invite_expires_at = expires_at
        member.invited_at = now
        member.version = int(member.version or 0) + 1
        db.commit()
        return {
            "campaignId": str(campaign.id),
            "companyId": str(company.id),
            "memberId": str(member.id),
            "inviteToken": raw,
            "expiresAt": member.invite_expires_at.isoformat(),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _load_invite_in_tx(db, *, tenant_id: int, token: str, lock: bool):
    campaign_id, member_id = _parse_invite_token(token)
    member_stmt = select(InternshipEnterpriseMember).where(
        InternshipEnterpriseMember.id == member_id,
        InternshipEnterpriseMember.tenant_id == tenant_id,
        InternshipEnterpriseMember.is_deleted.is_(False),
        InternshipEnterpriseMember.invite_token_hash == _invite_hash(token),
    )
    if lock:
        member_stmt = member_stmt.with_for_update()
    member = db.scalar(member_stmt)
    if not member or member.status != "INVITED":
        raise unauthorized("邀请链接无效、已使用或成员已停用")
    current = _now()
    if member.invite_expires_at is None or member.invite_expires_at <= current:
        raise unauthorized("邀请链接已过期")
    campaign = _get_campaign(db, campaign_id, tenant_id=tenant_id, lock=lock)
    _assert_invite_window(campaign, current, public_token=True)
    participation_stmt = select(InternshipCampaignEnterprise).where(
        InternshipCampaignEnterprise.tenant_id == tenant_id,
        InternshipCampaignEnterprise.campaign_id == campaign.id,
        InternshipCampaignEnterprise.company_id == member.company_id,
        InternshipCampaignEnterprise.is_deleted.is_(False),
    )
    if lock:
        participation_stmt = participation_stmt.with_for_update()
    participation = db.scalar(participation_stmt)
    if not participation or participation.status != "INVITED":
        raise unauthorized("企业邀请已撤销、已接受或状态已变化")
    company = _get_company(db, member.company_id, tenant_id=tenant_id, require_admission=True)
    user = db.scalar(
        select(User).where(
            User.id == member.user_id,
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )
    )
    if not user or (user.user_type or "").upper() != "ENTERPRISE_MENTOR":
        raise unauthorized("邀请账号不存在或身份无效")
    return campaign, participation, company, member, user


def inspect_invite(*, tenant_code: str, token: str):
    db = get_sessionmaker()()
    try:
        tenant = _tenant_by_code(db, tenant_code)
        campaign, _participation, company, member, user = _load_invite_in_tx(
            db, tenant_id=tenant.id, token=token, lock=False
        )
        phone_plain = decrypt_sensitive(user.phone_encrypted, "phone") if user.phone_encrypted else ""
        return {
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "schoolName": tenant.school_name,
            "campaignId": str(campaign.id),
            "campaignName": campaign.campaign_name,
            "companyId": str(company.id),
            "companyName": company.name,
            "inviteeName": user.real_name,
            "phoneMasked": mask_phone(phone_plain),
            "memberRole": member.member_role,
            "expiresAt": member.invite_expires_at.isoformat(),
        }
    finally:
        db.close()


def _claims(*, tenant, user, member) -> dict:
    return {
        "userId": f"db-{user.id}",
        "loginName": user.login_name,
        "realName": user.real_name,
        "userType": "ENTERPRISE_MENTOR",
        "tid": tenant.tenant_code,
        "tenantId": str(tenant.id),
        "tenantName": tenant.school_name,
        "enterpriseMemberId": str(member.id),
        "companyId": str(member.company_id),
        "memberRole": member.member_role,
        "activeContextId": f"enterprise-member:{member.id}",
        "currentRoleCode": "ENTERPRISE_MEMBER",
        "permissionVersion": f"u{int(user.version or 0)}|m{int(member.version or 0)}",
        "clientType": "ENTERPRISE_PC",
    }


def _token_result(*, tenant, user, member) -> dict:
    claims = _claims(tenant=tenant, user=user, member=member)
    return {
        "accessToken": create_access_token(claims),
        "refreshToken": issue_refresh(dict(claims)),
        "tokenType": "Bearer",
        "expiresIn": settings.JWT_EXPIRES_IN,
        "user": {
            "userId": f"db-{user.id}",
            "realName": user.real_name,
            "userType": user.user_type,
        },
        "context": {
            "tenantId": str(tenant.id),
            "tenantCode": tenant.tenant_code,
            "schoolName": tenant.school_name,
            "memberId": str(member.id),
            "companyId": str(member.company_id),
            "memberRole": member.member_role,
        },
    }


def accept_invite(*, tenant_code: str, token: str, phone: str, password: str):
    if len(password or "") < 8:
        raise AppException("VALIDATION_ERROR", "密码至少 8 位")
    phone_hash = hash_sensitive(str(phone or "").strip(), "phone")
    db = get_sessionmaker()()
    try:
        tenant = _tenant_by_code(db, tenant_code)
        campaign, participation, _company, member, user = _load_invite_in_tx(
            db, tenant_id=tenant.id, token=token, lock=True
        )
        if not phone_hash or not member.invited_phone_hash or phone_hash != member.invited_phone_hash:
            raise unauthorized("邀请手机号验证失败")
        if user.phone_hash and user.phone_hash != phone_hash:
            raise unauthorized("邀请手机号与企业账号不一致")
        now = _now()
        user.password_hash = hash_password(password)
        user.status = "ACTIVE"
        user.must_change_password = False
        user.version = int(user.version or 0) + 1
        member.status = "ACTIVE"
        member.accepted_at = member.accepted_at or now
        member.last_active_at = now
        member.invite_token_hash = None
        member.invite_expires_at = None
        member.version = int(member.version or 0) + 1
        participation.status = "ACCEPTED"
        participation.accepted_at = now
        participation.version = int(participation.version or 0) + 1
        db.flush()
        access_svc.issue_grant_in_tx(
            db,
            tenant_id=tenant.id,
            member_id=member.id,
            grant_type="RECRUITMENT",
            campaign_id=campaign.id,
            batch_id=campaign.batch_id,
            valid_from=now,
            valid_until=campaign.enterprise_access_end_at,
        )
        db.commit()
        return _token_result(tenant=tenant, user=user, member=member)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _active_members(db, *, tenant_id: int, user_id: int):
    return db.scalars(
        select(InternshipEnterpriseMember).where(
            InternshipEnterpriseMember.tenant_id == tenant_id,
            InternshipEnterpriseMember.user_id == user_id,
            InternshipEnterpriseMember.status == "ACTIVE",
            InternshipEnterpriseMember.is_deleted.is_(False),
        ).order_by(InternshipEnterpriseMember.is_primary.desc(), InternshipEnterpriseMember.id)
    ).all()


def login(*, tenant_code: str, login_name: str, password: str, member_id: int | None = None):
    db = get_sessionmaker()()
    try:
        tenant = _tenant_by_code(db, tenant_code)
        user = db.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.login_name == str(login_name or "").strip(),
                User.user_type == "ENTERPRISE_MENTOR",
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
            )
        )
        if not user or not verify_password(password or "", user.password_hash):
            raise unauthorized("学校编码、账号或密码不正确")
        members = _active_members(db, tenant_id=tenant.id, user_id=user.id)
        if not members:
            raise AppException("NO_PERMISSION", "企业成员身份已停用，请联系学校")
        if member_id is not None:
            member = next((item for item in members if item.id == _as_id(member_id)), None)
            if not member:
                raise AppException("NO_PERMISSION", "企业上下文不存在或不属于当前账号")
        elif len(members) == 1:
            member = members[0]
        else:
            company_ids = [item.company_id for item in members]
            companies = {
                row.id: row.name
                for row in db.scalars(
                    select(EmpCompany).where(
                        EmpCompany.tenant_id == tenant.id,
                        EmpCompany.id.in_(company_ids),
                        EmpCompany.is_deleted.is_(False),
                    )
                ).all()
            }
            raise AppException(
                "ENTERPRISE_CONTEXT_REQUIRED",
                "当前账号关联多个企业，请选择企业上下文后登录",
                details={
                    "contexts": [
                        {
                            "memberId": str(item.id),
                            "companyId": str(item.company_id),
                            "companyName": companies.get(item.company_id, ""),
                            "memberRole": item.member_role,
                        }
                        for item in members
                    ]
                },
                http_status=409,
            )
        _require_company_admission_for_auth(
            db,
            tenant_id=tenant.id,
            company_id=member.company_id,
        )
        member.last_active_at = _now()
        db.commit()
        return _token_result(tenant=tenant, user=user, member=member)
    finally:
        db.close()


def validate_enterprise_claims(claims: dict) -> tuple[object, User, InternshipEnterpriseMember]:
    if (claims.get("userType") or "").upper() != "ENTERPRISE_MENTOR":
        raise unauthorized("企业认证令牌无效")
    if jti_blocked(claims.get("jti")):
        raise unauthorized("令牌已登出失效，请重新登录")
    raw_user_id = str(claims.get("userId") or "")
    raw_tenant_id = str(claims.get("tenantId") or "")
    raw_member_id = str(claims.get("enterpriseMemberId") or "")
    if not raw_user_id.startswith("db-") or not raw_user_id[3:].isdigit() or not raw_tenant_id.isdigit() or not raw_member_id.isdigit():
        raise unauthorized("企业认证令牌无效")
    db = get_sessionmaker()()
    try:
        tenant = db.scalar(
            select(Tenant).where(
                Tenant.id == int(raw_tenant_id),
                Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
                Tenant.is_deleted.is_(False),
            )
        )
        user = db.scalar(
            select(User).where(
                User.id == int(raw_user_id[3:]),
                User.tenant_id == int(raw_tenant_id),
                User.user_type == "ENTERPRISE_MENTOR",
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
            )
        )
        member = db.scalar(
            select(InternshipEnterpriseMember).where(
                InternshipEnterpriseMember.id == int(raw_member_id),
                InternshipEnterpriseMember.tenant_id == int(raw_tenant_id),
                InternshipEnterpriseMember.user_id == int(raw_user_id[3:]),
                InternshipEnterpriseMember.status == "ACTIVE",
                InternshipEnterpriseMember.is_deleted.is_(False),
            )
        )
        if not tenant or not user or not member:
            raise unauthorized("企业账号、学校或成员身份已失效")
        if str(member.company_id) != str(claims.get("companyId") or ""):
            raise unauthorized("企业上下文已变化，请重新登录")
        _require_company_admission_for_auth(
            db,
            tenant_id=tenant.id,
            company_id=member.company_id,
        )
        expected_version = f"u{int(user.version or 0)}|m{int(member.version or 0)}"
        if claims.get("permissionVersion") != expected_version:
            raise unauthorized("企业成员权限已更新，请重新登录")
        return tenant, user, member
    finally:
        db.close()


def refresh(*, refresh_token: str):
    claims = consume_refresh(refresh_token)
    if not claims:
        raise unauthorized("refreshToken 无效或已使用，请重新登录")
    tenant, user, member = validate_enterprise_claims(claims)
    return _token_result(tenant=tenant, user=user, member=member)


def decode_and_validate_access(token: str) -> tuple[dict, object, User, InternshipEnterpriseMember]:
    claims = decode_token(token)
    tenant, user, member = validate_enterprise_claims(claims)
    return claims, tenant, user, member
