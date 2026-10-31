"""School-owned member bindings and explicit batch collaboration access; no new identity store."""
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.models import InternshipBatch, InternshipEnterpriseContact, InternshipRecord, StudentProfile, User
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.models.internship_enterprise_portal import (InternshipCampaignEnterprise, InternshipEnterpriseAccessGrant,
    InternshipEnterpriseMember, InternshipRecruitmentCampaign)
from app.modules.internship.services import internship_enterprise_access_service as access
from app.modules.internship.services import internship_enterprise_member_service as members
from app.modules.internship.services.internship_enterprise_service import assert_company_writable
from app.modules.internship.services.internship_service import assert_admin_tenant
from app.services.db_service import _as_id, _tid, audit_insert_in_session, session


def require_school_manager(user):
    enforce_permission(user, "internship.enterprise.manage")
    assert_admin_tenant(user, "企业成员及实习协同授权维护")
    return user


def _company(db, company_id, user):
    require_school_manager(user)
    company = members._get_company(db, company_id, tenant_id=_tid())
    assert_company_writable(db, company.id, user)
    return company


def _member(db, company_id, member_id, user, *, lock=False):
    _company(db, company_id, user)
    member = members._get_member(db, member_id, tenant_id=_tid(), lock=lock)
    if member.company_id != _as_id(company_id):
        raise not_found("成员不属于当前企业")
    return member


def _version(member, expected):
    if int(member.version or 0) != expected:
        raise AppException("DATA_CONFLICT", "成员资料已变化，请保留输入并重新读取核对", http_status=409)


def _audit(db, user, member, action, detail):
    from app.modules.internship.services.internship_audit_service import add_audit
    add_audit(db, target_type="ENTERPRISE_MEMBER", target_id=member.id,
              action=action, user=user, detail=detail)

def list_members(company_id, user, *, page=1, page_size=20):
    with session() as db:
        _company(db, company_id, user)
        conditions = (InternshipEnterpriseMember.tenant_id == _tid(),
            InternshipEnterpriseMember.company_id == _as_id(company_id), InternshipEnterpriseMember.is_deleted.is_(False))
        total = db.scalar(select(func.count()).select_from(InternshipEnterpriseMember).where(*conditions)) or 0
        rows = db.execute(select(InternshipEnterpriseMember, User.real_name, InternshipEnterpriseContact.name)
            .join(User, (User.id == InternshipEnterpriseMember.user_id) & (User.tenant_id == _tid()) & User.is_deleted.is_(False))
            .outerjoin(InternshipEnterpriseContact, (InternshipEnterpriseContact.id == InternshipEnterpriseMember.contact_id)
                & (InternshipEnterpriseContact.tenant_id == _tid()) & InternshipEnterpriseContact.is_deleted.is_(False))
            .where(*conditions).order_by(InternshipEnterpriseMember.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
        return {"items": [{**members._row(member), "realName": name, "contactName": contact or ""}
            for member, name, contact in rows], "total": int(total), "page": page, "pageSize": page_size}


def bind_contact(company_id, member_id, contact_id, expected_version, user):
    with session() as db:
        member = _member(db, company_id, member_id, user, lock=True)
        _version(member, expected_version)
        contact = members._get_contact(db, contact_id, tenant_id=_tid(), company_id=member.company_id, lock=True)
        if contact.status != "ACTIVE" or (member.member_role == "MENTOR" and contact.contact_type != "MENTOR"):
            raise AppException("VALIDATION_ERROR", "请选择本企业有效的导师联系人")
        before = member.contact_id
        if before != contact.id:
            member.contact_id = contact.id
            member.version = int(member.version or 0) + 1
            _audit(db, user, member, "ENTERPRISE_MEMBER_CONTACT_BIND",
                {"beforeContactId": str(before or ""), "contactId": str(contact.id), "version": member.version})
            db.commit()
        return {**members._row(member), "contactName": contact.name}


def change_status(company_id, member_id, target, expected_version, reason, user):
    with session() as db:
        member = _member(db, company_id, member_id, user, lock=True)
        _version(member, expected_version)
        if target not in {"ACTIVE", "DISABLED"} or len(reason.strip()) < 2:
            raise AppException("VALIDATION_ERROR", "请明确成员启停动作并填写原因")
        if target == "ACTIVE" and not member.accepted_at:
            raise AppException("DATA_CONFLICT", "尚未接受邀请的成员必须本人激活，学校不能代激活", http_status=409)
        if member.status != target:
            before = member.status
            member.status = target
            if target == "DISABLED":
                member.invite_token_hash = None
                member.invite_expires_at = None
            member.version = int(member.version or 0) + 1
            _audit(db, user, member, "ENTERPRISE_MEMBER_STATUS_CHANGE",
                {"beforeStatus": before, "status": target, "reason": reason, "version": member.version})
            db.commit()
        return members._row(member)


def list_grants(company_id, member_id, user, *, page=1, page_size=20):
    with session() as db:
        member = _member(db, company_id, member_id, user)
        conditions = (InternshipEnterpriseAccessGrant.tenant_id == _tid(),
            InternshipEnterpriseAccessGrant.company_id == member.company_id,
            InternshipEnterpriseAccessGrant.member_id == member.id,
            InternshipEnterpriseAccessGrant.grant_type == "INTERNSHIP_COLLAB",
            InternshipEnterpriseAccessGrant.campaign_id.is_(None), InternshipEnterpriseAccessGrant.is_deleted.is_(False))
        total = db.scalar(select(func.count()).select_from(InternshipEnterpriseAccessGrant).where(*conditions)) or 0
        rows = db.execute(select(InternshipEnterpriseAccessGrant, InternshipBatch.batch_name)
            .join(InternshipBatch, (InternshipBatch.id == InternshipEnterpriseAccessGrant.batch_id)
                & (InternshipBatch.tenant_id == _tid()) & InternshipBatch.is_deleted.is_(False))
            .where(*conditions).order_by(InternshipEnterpriseAccessGrant.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
        return {"items": [{**access._row(grant), "batchName": name} for grant, name in rows],
            "total": int(total), "page": page, "pageSize": page_size}


def issue_collaboration(company_id, member_id, batch_id, valid_from, valid_until, expected_member_version, user):
    with session() as db:
        member = _member(db, company_id, member_id, user, lock=True)
        _version(member, expected_member_version)
        if member.member_role == "MENTOR":
            if not member.contact_id:
                raise AppException("VALIDATION_ERROR", "请先为该企业导师绑定联系人")
            contact = members._get_contact(db, member.contact_id, tenant_id=_tid(), company_id=member.company_id, lock=True)
            if contact.status != "ACTIVE" or contact.contact_type != "MENTOR":
                raise AppException("VALIDATION_ERROR", "绑定的企业导师联系人已失效，请重新核对")
        participation = db.scalar(select(InternshipCampaignEnterprise.id)
            .join(InternshipRecruitmentCampaign, InternshipRecruitmentCampaign.id == InternshipCampaignEnterprise.campaign_id)
            .where(InternshipCampaignEnterprise.tenant_id == _tid(), InternshipCampaignEnterprise.company_id == member.company_id,
                InternshipCampaignEnterprise.status == "ACCEPTED", InternshipCampaignEnterprise.is_deleted.is_(False),
                InternshipRecruitmentCampaign.tenant_id == _tid(), InternshipRecruitmentCampaign.batch_id == _as_id(batch_id),
                InternshipRecruitmentCampaign.is_deleted.is_(False)))
        if not participation:
            placement = select(InternshipRecord.id).join(StudentProfile, StudentProfile.id == InternshipRecord.student_id).join(
                InternshipPlacementSnapshot, InternshipPlacementSnapshot.id == InternshipRecord.current_placement_snapshot_id).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == _as_id(batch_id),
                InternshipRecord.enterprise_id == member.company_id, InternshipRecord.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                InternshipPlacementSnapshot.tenant_id == _tid(), InternshipPlacementSnapshot.record_id == InternshipRecord.id,
                InternshipPlacementSnapshot.batch_id == InternshipRecord.batch_id,
                InternshipPlacementSnapshot.company_id == InternshipRecord.enterprise_id,
                InternshipPlacementSnapshot.position_id == InternshipRecord.position_id)
            if member.member_role == 'MENTOR':
                placement = placement.where(InternshipRecord.mentor_contact_id == member.contact_id)
            if not db.scalar(placement.limit(1)):
                raise AppException("DATA_CONFLICT", "企业须已接受该批次招聘参与，或已有本批次正式安置关系，才能开通协同", http_status=409)
        # API timestamps carry an explicit offset; storage and the shared access service use UTC.
        start = valid_from.astimezone(timezone.utc).replace(tzinfo=None)
        end = valid_until.astimezone(timezone.utc).replace(tzinfo=None)
        if end <= datetime.utcnow():
            raise AppException("VALIDATION_ERROR", "授权截止时间必须晚于当前时间")
        existing = db.scalar(select(InternshipEnterpriseAccessGrant.id).where(
            InternshipEnterpriseAccessGrant.tenant_id == _tid(), InternshipEnterpriseAccessGrant.member_id == member.id,
            InternshipEnterpriseAccessGrant.grant_type == "INTERNSHIP_COLLAB", InternshipEnterpriseAccessGrant.batch_id == _as_id(batch_id),
            InternshipEnterpriseAccessGrant.campaign_id.is_(None), InternshipEnterpriseAccessGrant.is_deleted.is_(False)).with_for_update())
        if existing:
            raise AppException("DATA_CONFLICT", "本成员该批次已有授权记录，请核对原有效期；不会自动续期或恢复", http_status=409)
        grant = access.issue_grant_in_tx(db, member_id=member.id, grant_type="INTERNSHIP_COLLAB",
            batch_id=_as_id(batch_id), campaign_id=None, valid_from=start, valid_until=end, tenant_id=_tid())
        _audit(db, user, member, "ENTERPRISE_COLLABORATION_GRANT_ISSUE",
            {"grantId": str(grant.id), "batchId": str(batch_id), "validFrom": start.isoformat(), "validUntil": end.isoformat()})
        db.commit()
        return access._row(grant)


def revoke_collaboration(company_id, member_id, grant_id, expected_version, reason, user):
    with session() as db:
        member = _member(db, company_id, member_id, user, lock=True)
        grant = access._get_grant(db, grant_id, tenant_id=_tid(), lock=True)
        if (grant.member_id != member.id or grant.company_id != member.company_id
                or grant.grant_type != "INTERNSHIP_COLLAB" or grant.campaign_id is not None):
            raise not_found("授权不属于当前成员的实习协同范围")
        access.revoke_grant_in_tx(db, grant, expected_version=expected_version, reason=reason,
            revoked_by_user_id=_as_id(str(user["userId"]).removeprefix("db-")))
        _audit(db, user, member, "ENTERPRISE_COLLABORATION_GRANT_REVOKE",
            {"grantId": str(grant.id), "batchId": str(grant.batch_id), "reason": reason, "version": grant.version})
        db.commit()
        return access._row(grant)
