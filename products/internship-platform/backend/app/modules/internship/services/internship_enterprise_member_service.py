"""EnterpriseMember authority service.

Enterprise members always reuse tenant-scoped `t_user`; this module never creates a second
login table. Invite-token activation is deliberately deferred to A01-6.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import EmpCompany, InternshipEnterpriseContact, User
from app.models.internship_enterprise_portal import InternshipEnterpriseMember
from app.modules.internship.enterprise_collaboration_contract import ENTERPRISE_MEMBER_ROLES
from app.services.db_service import _as_id, _iso, _tid, session


def _get_user(db, user_id: int, *, tenant_id: int):
    user = db.scalar(
        select(User).where(
            User.id == _as_id(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )
    )
    if not user:
        raise not_found("企业成员账号不存在或不在当前租户")
    return user


def _get_company(db, company_id: int, *, tenant_id: int):
    company = db.scalar(
        select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id),
            EmpCompany.tenant_id == tenant_id,
            EmpCompany.is_deleted.is_(False),
        )
    )
    if not company:
        raise not_found("企业不存在或不在当前租户")
    return company


def _get_contact(db, contact_id: int, *, tenant_id: int, company_id: int):
    contact = db.scalar(
        select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.id == _as_id(contact_id),
            InternshipEnterpriseContact.tenant_id == tenant_id,
            InternshipEnterpriseContact.company_id == company_id,
            InternshipEnterpriseContact.is_deleted.is_(False),
        )
    )
    if not contact:
        raise AppException("VALIDATION_ERROR", "企业联系人不存在或不属于该企业")
    return contact


def _get_member(db, member_id: int, *, tenant_id: int, lock: bool = False):
    stmt = select(InternshipEnterpriseMember).where(
        InternshipEnterpriseMember.id == _as_id(member_id),
        InternshipEnterpriseMember.tenant_id == tenant_id,
        InternshipEnterpriseMember.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    member = db.scalar(stmt)
    if not member:
        raise not_found("企业成员不存在或不在当前租户")
    return member


def _row(member: InternshipEnterpriseMember, user: User | None = None):
    return {
        "id": str(member.id),
        "companyId": str(member.company_id),
        "userId": str(member.user_id),
        "contactId": str(member.contact_id) if member.contact_id else "",
        "memberRole": member.member_role,
        "status": member.status,
        "isPrimary": bool(member.is_primary),
        "userStatus": user.status if user else "",
        "userType": user.user_type if user else "",
        "acceptedAt": _iso(member.accepted_at),
        "lastActiveAt": _iso(member.last_active_at),
        "version": int(member.version or 0),
    }


def create_member(
    *,
    company_id: int,
    user_id: int,
    member_role: str,
    contact_id: int | None = None,
    is_primary: bool = False,
    status: str = "INVITED",
):
    tenant_id = _tid()
    role = (member_role or "").upper()
    if role not in ENTERPRISE_MEMBER_ROLES:
        raise AppException("VALIDATION_ERROR", "memberRole 必须是 COMPANY_ADMIN/HR/MENTOR")
    initial_status = (status or "INVITED").upper()
    if initial_status not in {"INVITED", "ACTIVE"}:
        raise AppException("VALIDATION_ERROR", "新成员初始状态只能是 INVITED/ACTIVE")

    with session() as db:
        _get_company(db, company_id, tenant_id=tenant_id)
        user = _get_user(db, user_id, tenant_id=tenant_id)
        if user.user_type != "ENTERPRISE_MENTOR":
            raise AppException("DATA_CONFLICT", "企业成员必须复用 ENTERPRISE_MENTOR 类型 t_user")
        if contact_id is not None:
            _get_contact(db, contact_id, tenant_id=tenant_id, company_id=_as_id(company_id))

        existing = db.scalar(
            select(InternshipEnterpriseMember).where(
                InternshipEnterpriseMember.tenant_id == tenant_id,
                InternshipEnterpriseMember.company_id == _as_id(company_id),
                InternshipEnterpriseMember.user_id == user.id,
                InternshipEnterpriseMember.is_deleted.is_(False),
            ).with_for_update()
        )
        if existing:
            return _row(existing, user)

        member = InternshipEnterpriseMember(
            tenant_id=tenant_id,
            company_id=_as_id(company_id),
            user_id=user.id,
            contact_id=_as_id(contact_id) if contact_id is not None else None,
            member_role=role,
            status=initial_status,
            is_primary=bool(is_primary),
            invited_at=datetime.utcnow() if initial_status == "INVITED" else None,
            accepted_at=datetime.utcnow() if initial_status == "ACTIVE" else None,
        )
        db.add(member)
        db.flush()
        db.commit()
        return _row(member, user)


def resolve_member_for_user(*, user_id: int, company_id: int | None = None, require_active: bool = True):
    tenant_id = _tid()
    with session() as db:
        user = _get_user(db, user_id, tenant_id=tenant_id)
        if require_active and user.status != "ACTIVE":
            raise AppException("NO_PERMISSION", "企业账号已停用或锁定")
        stmt = select(InternshipEnterpriseMember).where(
            InternshipEnterpriseMember.tenant_id == tenant_id,
            InternshipEnterpriseMember.user_id == user.id,
            InternshipEnterpriseMember.is_deleted.is_(False),
        )
        if company_id is not None:
            stmt = stmt.where(InternshipEnterpriseMember.company_id == _as_id(company_id))
        rows = db.scalars(stmt.order_by(InternshipEnterpriseMember.is_primary.desc(), InternshipEnterpriseMember.id)).all()
        rows = [member for member in rows if not require_active or member.status == "ACTIVE"]
        if not rows:
            raise AppException("NO_PERMISSION", "当前账号没有有效企业成员身份")
        if company_id is None and len(rows) != 1:
            raise AppException("DATA_CONFLICT", "当前账号关联多个企业，必须由服务端上下文明确企业范围")
        member = rows[0]
        return _row(member, user)


def set_member_status(member_id: int, target_status: str, *, expected_version: int):
    target = (target_status or "").upper()
    if target not in {"ACTIVE", "DISABLED"}:
        raise AppException("VALIDATION_ERROR", "成员状态只能切换 ACTIVE/DISABLED")
    tenant_id = _tid()
    with session() as db:
        member = _get_member(db, member_id, tenant_id=tenant_id, lock=True)
        current = int(member.version or 0)
        if int(expected_version) != current:
            raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")
        if member.status == target:
            return _row(member, _get_user(db, member.user_id, tenant_id=tenant_id))
        if member.status == "INVITED" and target == "DISABLED":
            member.status = "DISABLED"
        elif member.status in {"INVITED", "DISABLED"} and target == "ACTIVE":
            member.status = "ACTIVE"
            member.accepted_at = member.accepted_at or datetime.utcnow()
        elif member.status == "ACTIVE" and target == "DISABLED":
            member.status = "DISABLED"
        else:
            raise AppException("DATA_CONFLICT", f"成员状态 {member.status} 不可迁移到 {target}")
        member.version = current + 1
        db.commit()
        return _row(member, _get_user(db, member.user_id, tenant_id=tenant_id))
