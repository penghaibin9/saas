"""Enterprise-only facade over canonical internship company/position facts.

This module never trusts a client companyId/campaignId as resource authority. The router first
resolves EnterpriseContext from the signed member + active Grant + accepted campaign participation,
then every query is constrained again by tenant/company/campaign.

No second Company/Job/Application fact is introduced. Enterprise position writes can only produce
DRAFT/PENDING; PUBLISH remains the existing school Authority.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseContact, InternshipPosition
from app.models.internship_enterprise_portal import (
    InternshipCampaignEnterprise,
    InternshipEnterpriseAccessGrant,
    InternshipRecruitmentCampaign,
)
from app.modules.internship.services.internship_recruitment_window_guard import (
    assert_campaign_operation_window,
)
from app.modules.internship.services.internship_enterprise_access_service import effective_grant_status
from app.services import file_business_binding_service
from app.services.db_service import _iso

_EDITOR_ROLES = {"COMPANY_ADMIN", "HR"}

_POSITION_FIELDS = {
    "title": "title",
    "category": "category",
    "headcount": "headcount",
    "workLocation": "work_location",
    "workAddress": "work_address",
    "majorRequirement": "major_requirement",
    "gradeRequirement": "grade_requirement",
    "mentorContactId": "mentor_contact_id",
    "workContent": "work_content",
    "remark": "remark",
    "dailyHours": "daily_hours",
    "weeklyHours": "weekly_hours",
    "shiftType": "shift_type",
    "nightShift": "night_shift",
    "overtimeAllowed": "overtime_allowed",
    "restDaysPerWeek": "rest_days_per_week",
    "remunerationType": "remuneration_type",
    "remunerationAmount": "remuneration_amount",
    "remunerationCycle": "remuneration_cycle",
    "salaryRange": "salary_range",
    "subsidy": "subsidy",
    "accommodationProvided": "accommodation_provided",
    "mealProvided": "meal_provided",
    "hazardousFlag": "hazardous_flag",
    "specialEquipment": "special_equipment",
    "prohibitedReason": "prohibited_reason",
}


def _role(context) -> str:
    return str(context.member_role or "").upper()


def _assert_editor(context) -> None:
    if _role(context) not in _EDITOR_ROLES:
        raise no_permission("仅企业管理员或 HR 可维护招聘资料和岗位")


def _audit(db, context, *, target_type: str, target_id: int, action: str, detail=None) -> None:
    db.add(
        InternshipAuditTrail(
            tenant_id=context.tenant_id,
            target_id=target_id,
            target_type=target_type,
            action=action,
            operator_name=f"企业成员#{context.member_id}",
            detail_json={
                **(detail or {}),
                "enterpriseMemberId": str(context.member_id),
                "enterpriseUserId": str(context.user_id),
                "companyId": str(context.company_id),
            },
            occurred_at=datetime.utcnow(),
        )
    )


def _company(db, context, *, lock: bool = False) -> EmpCompany:
    q = select(EmpCompany).where(
        EmpCompany.id == context.company_id,
        EmpCompany.tenant_id == context.tenant_id,
        EmpCompany.is_deleted.is_(False),
    )
    row = db.scalar(q.with_for_update() if lock else q)
    if not row:
        raise not_found("企业主档不存在或不在当前企业上下文")
    return row


def _company_row(row: EmpCompany) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "logoFileId": row.logo_file_id,
        "coverFileId": row.cover_file_id,
        "shortName": row.short_name or "",
        "shortIntro": row.short_intro or "",
        "website": row.website or "",
        "mainBusiness": row.main_business or "",
        "establishedYear": row.established_year,
        "industry": row.industry or "",
        "nature": row.nature or "",
        "scale": row.scale or "",
        "region": row.region or "",
        "city": row.city or "",
        "address": row.address or "",
        "qualificationStatus": row.qualification_status,
        "coopStatus": row.coop_status,
        "accessValidUntil": _iso(row.access_valid_until),
        "blacklist": bool(row.blacklist),
        "schoolReview": row.review_comment or "",
        "version": int(row.version or 0),
    }


def company_profile_in_tx(db, *, context) -> dict:
    return _company_row(_company(db, context))


def update_company_profile_in_tx(db, *, context, payload: dict[str, Any]) -> dict:
    _assert_editor(context)
    if payload.get("expectedVersion") is None:
        raise AppException("DATA_CONFLICT", "保存企业资料必须携带当前版本")
    row = _company(db, context, lock=True)
    if int(row.version or 0) != int(payload["expectedVersion"]):
        raise AppException("DATA_CONFLICT", "企业资料已更新，请刷新后重试")

    short_name = str(payload.get("shortName") or "").strip()
    short_intro = str(payload.get("shortIntro") or "").strip()
    website = str(payload.get("website") or "").strip()
    main_business = str(payload.get("mainBusiness") or "").strip()
    address = str(payload.get("address") or "").strip()
    year = payload.get("establishedYear")
    if website and not (website.startswith("https://") or website.startswith("http://")):
        raise AppException("VALIDATION_ERROR", "企业官网必须使用 http:// 或 https://")
    if year not in (None, ""):
        try:
            year = int(year)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "成立年份格式不正确") from exc
        if year < 1800 or year > datetime.utcnow().year + 1:
            raise AppException("VALIDATION_ERROR", "成立年份超出合理范围")
    else:
        year = None

    row.short_name = short_name or None
    row.short_intro = short_intro or None
    row.website = website or None
    row.main_business = main_business or None
    row.established_year = year
    row.address = address or None

    logo_file_id = payload.get("logoFileId")
    if logo_file_id is not None and str(logo_file_id or "").strip() != str(row.logo_file_id or ""):
        fid = str(logo_file_id or "").strip()
        if not fid:
            row.logo_file_id = None
        else:
            file_business_binding_service.bind_file_to_business(
                db,
                file_id=fid,
                biz_type="INTERNSHIP_ENTERPRISE_PROFILE",
                biz_id=str(row.id),
                actor=get_current_user_ctx() or {},
                subject_type="ENTERPRISE",
                subject_id=str(row.id),
                relation_type="LOGO",
                module_code="INTERNSHIP",
                scope={"companyId": str(row.id)},
            )
            row.logo_file_id = fid

    row.version = int(row.version or 0) + 1
    _audit(
        db,
        context,
        target_type="ENTERPRISE",
        target_id=row.id,
        action="ENTERPRISE_PUBLIC_PROFILE_UPDATE",
        detail={"version": int(row.version or 0)},
    )
    db.flush()
    return _company_row(row)


def _campaign(db, context, *, lock: bool = False) -> InternshipRecruitmentCampaign:
    stmt = select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.id == context.campaign_id,
            InternshipRecruitmentCampaign.tenant_id == context.tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        )
    row = db.scalar(stmt.with_for_update().execution_options(populate_existing=True) if lock else stmt)
    if not row:
        raise not_found("招聘季不存在或不在当前企业上下文")
    return row


def _writable_campaign(db, context) -> InternshipRecruitmentCampaign:
    campaign = _campaign(db, context, lock=True)
    if str(campaign.status or "").upper() != "OPEN":
        raise AppException("DATA_CONFLICT", "招聘季当前不可编辑，岗位记录仅供查阅")
    return campaign


def _campaign_row(row: InternshipRecruitmentCampaign, participation_status: str | None = None) -> dict:
    return {
        "id": str(row.id),
        "campaignId": str(row.id),
        "campaignName": row.campaign_name,
        "name": row.campaign_name,
        "status": row.status,
        "roundNo": row.round_no,
        "batchId": str(row.batch_id),
        "participationStatus": participation_status,
        "positionSubmitStartAt": _iso(row.position_submit_start_at),
        "positionSubmitEndAt": _iso(row.position_submit_end_at),
        "studentSelectStartAt": _iso(row.student_select_start_at),
        "studentSelectEndAt": _iso(row.student_select_end_at),
        "enterpriseDecisionStartAt": _iso(row.enterprise_decision_start_at),
        "enterpriseDecisionEndAt": _iso(row.enterprise_decision_end_at),
        "enterpriseAccessEndAt": _iso(row.enterprise_access_end_at),
    }


def campaigns_for_principal_in_tx(db, *, principal) -> list[dict]:
    rows = db.execute(
        select(InternshipCampaignEnterprise, InternshipRecruitmentCampaign)
        .join(
            InternshipRecruitmentCampaign,
            InternshipRecruitmentCampaign.id == InternshipCampaignEnterprise.campaign_id,
        )
        .where(
            InternshipCampaignEnterprise.tenant_id == principal.tenant_id,
            InternshipCampaignEnterprise.company_id == principal.company_id,
            InternshipCampaignEnterprise.is_deleted.is_(False),
            InternshipRecruitmentCampaign.tenant_id == principal.tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        )
        .order_by(InternshipRecruitmentCampaign.id.desc())
    ).all()
    # Same member/company and exact recruitment or collaboration scope as context resolution.
    # Keep company participation visible even when this member cannot enter it.
    grants = db.scalars(select(InternshipEnterpriseAccessGrant).where(
        InternshipEnterpriseAccessGrant.tenant_id == principal.tenant_id,
        InternshipEnterpriseAccessGrant.member_id == principal.member_id,
        InternshipEnterpriseAccessGrant.company_id == principal.company_id,
        InternshipEnterpriseAccessGrant.is_deleted.is_(False),
    )).all()
    by_scope = {}
    for grant in grants:
        by_scope.setdefault((grant.grant_type, grant.campaign_id, grant.batch_id), grant)
    now = datetime.utcnow()
    result = []
    for participation, campaign in rows:
        grant = by_scope.get(("RECRUITMENT", campaign.id, campaign.batch_id))
        collab = by_scope.get(("INTERNSHIP_COLLAB", None, campaign.batch_id))
        status = effective_grant_status(grant, now=now) if grant else "MISSING"
        result.append({
            **_campaign_row(campaign, participation.status),
            "recruitmentAccessStatus": status,
            "recruitmentAvailable": participation.status == "ACCEPTED" and status == "ACTIVE",
            "collaborationAvailable": bool(collab and effective_grant_status(collab, now=now) == "ACTIVE"),
        })
    return result


def context_projection_in_tx(db, *, context) -> dict:
    campaign = _campaign(db, context)
    now = datetime.utcnow()
    collab = db.scalar(
        select(InternshipEnterpriseAccessGrant.id).where(
            InternshipEnterpriseAccessGrant.tenant_id == context.tenant_id,
            InternshipEnterpriseAccessGrant.member_id == context.member_id,
            InternshipEnterpriseAccessGrant.company_id == context.company_id,
            InternshipEnterpriseAccessGrant.grant_type == "INTERNSHIP_COLLAB",
            InternshipEnterpriseAccessGrant.batch_id == context.batch_id,
            InternshipEnterpriseAccessGrant.status == "ACTIVE",
            InternshipEnterpriseAccessGrant.valid_from <= now,
            InternshipEnterpriseAccessGrant.valid_until >= now,
            InternshipEnterpriseAccessGrant.is_deleted.is_(False),
        )
    )
    recruitment_write = _role(context) in _EDITOR_ROLES and str(campaign.status or "").upper() == "OPEN"
    return {
        "tenantId": str(context.tenant_id),
        "tenantCode": context.tenant_code,
        "memberId": str(context.member_id),
        "memberRole": context.member_role,
        "companyId": str(context.company_id),
        "campaignId": str(context.campaign_id),
        "campaignName": campaign.campaign_name,
        "campaignStatus": campaign.status,
        "batchId": str(context.batch_id),
        "grantId": str(context.grant_id),
        "grantType": context.grant_type,
        "capabilities": {
            "recruitmentWrite": bool(recruitment_write),
            "internshipCollab": bool(collab),
        },
    }


def _position_query(context):
    return select(InternshipPosition).where(
        InternshipPosition.tenant_id == context.tenant_id,
        InternshipPosition.company_id == context.company_id,
        InternshipPosition.campaign_id == context.campaign_id,
        InternshipPosition.is_deleted.is_(False),
    )


def _position(db, context, position_id: int, *, lock: bool = False) -> InternshipPosition:
    q = _position_query(context).where(InternshipPosition.id == int(position_id))
    row = db.scalar(q.with_for_update() if lock else q)
    if not row:
        raise not_found("岗位不存在或不属于当前企业招聘季")
    return row


def _position_row(row: InternshipPosition) -> dict:
    return {
        "id": str(row.id),
        "campaignId": str(row.campaign_id) if row.campaign_id else None,
        "sourceType": row.source_type,
        "title": row.title,
        "category": row.category or "",
        "headcount": int(row.headcount or 0),
        "allocatedCount": int(row.allocated_count or 0),
        "workLocation": row.work_location or "",
        "workAddress": row.work_address or "",
        "majorRequirement": row.major_requirement or "",
        "gradeRequirement": row.grade_requirement or "",
        "mentorContactId": str(row.mentor_contact_id) if row.mentor_contact_id else None,
        "workContent": row.work_content or "",
        "remark": row.remark or "",
        "dailyHours": row.daily_hours,
        "weeklyHours": row.weekly_hours,
        "shiftType": row.shift_type,
        "nightShift": row.night_shift,
        "overtimeAllowed": row.overtime_allowed,
        "restDaysPerWeek": row.rest_days_per_week,
        "remunerationType": row.remuneration_type,
        "remunerationAmount": row.remuneration_amount,
        "remunerationCycle": row.remuneration_cycle,
        "salaryRange": row.salary_range or "",
        "subsidy": row.subsidy or "",
        "accommodationProvided": row.accommodation_provided,
        "mealProvided": row.meal_provided,
        "hazardousFlag": row.hazardous_flag,
        "specialEquipment": row.special_equipment or "",
        "prohibitedReason": row.prohibited_reason or "",
        "status": row.status,
        "version": int(row.version or 0),
        "updatedAt": _iso(row.updated_at),
    }


def list_positions_in_tx(db, *, context, page: int, page_size: int, status: str | None = None) -> dict:
    q = _position_query(context)
    if status:
        q = q.where(InternshipPosition.status == str(status).upper())
    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    rows = db.scalars(
        q.order_by(InternshipPosition.id.desc())
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": [_position_row(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


def school_returns_in_tx(db, *, context, position_ids: list[int]) -> dict[int, dict]:
    """Only deliberately enterprise-visible return notes, never general staff audit data."""
    if not position_ids:
        return {}
    latest = select(func.max(InternshipAuditTrail.id)).where(
        InternshipAuditTrail.tenant_id == context.tenant_id,
        InternshipAuditTrail.target_type == "POSITION",
        InternshipAuditTrail.target_id.in_(position_ids),
        InternshipAuditTrail.action == "STATUS_RETURN",
        InternshipAuditTrail.detail_json["enterpriseVisible"].as_boolean().is_(True),
    ).group_by(InternshipAuditTrail.target_id)
    rows = db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.id.in_(latest))).all()
    return {row.target_id: {
        "id": str(row.id), "reason": str((row.detail_json or {}).get("reason") or ""),
        "returnedAt": _iso(row.occurred_at),
    } for row in rows}


def get_position_in_tx(db, *, context, position_id: int) -> dict:
    row = _position(db, context, position_id)
    return {**_position_row(row), "schoolReturn": school_returns_in_tx(db, context=context, position_ids=[row.id]).get(row.id)}


def _coerce_number(value, field: str, *, integer: bool = False, minimum=None, maximum=None):
    if value is None or value == "":
        return None
    try:
        parsed = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{field}格式不正确") from exc
    if minimum is not None and parsed < minimum:
        raise AppException("VALIDATION_ERROR", f"{field}不能小于 {minimum}")
    if maximum is not None and parsed > maximum:
        raise AppException("VALIDATION_ERROR", f"{field}不能大于 {maximum}")
    return parsed


def _normalized_position_values(payload: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for src, column in _POSITION_FIELDS.items():
        if src not in payload:
            continue
        value = payload.get(src)
        if src == "headcount":
            value = _coerce_number(value, "招聘人数", integer=True, minimum=1, maximum=100000)
        elif src == "dailyHours":
            value = _coerce_number(value, "每日工时", minimum=0, maximum=24)
        elif src == "weeklyHours":
            value = _coerce_number(value, "每周工时", minimum=0, maximum=168)
        elif src == "restDaysPerWeek":
            value = _coerce_number(value, "每周休息天数", minimum=0, maximum=7)
        elif src == "remunerationAmount":
            value = _coerce_number(value, "报酬金额", minimum=0)
        elif src == "mentorContactId":
            if value in (None, ""):
                value = None
            else:
                value = _coerce_number(value, "企业导师", integer=True, minimum=1)
        elif isinstance(value, str):
            value = value.strip() or None
        values[column] = value
    title = values.get("title")
    if creating and not title:
        raise AppException("VALIDATION_ERROR", "岗位名称必填")
    return values


def _validate_mentor_contact_in_tx(db, *, context, mentor_contact_id: int | None) -> int | None:
    if mentor_contact_id is None:
        return None
    contact = db.scalar(select(InternshipEnterpriseContact).where(
        InternshipEnterpriseContact.id == int(mentor_contact_id),
        InternshipEnterpriseContact.tenant_id == context.tenant_id,
        InternshipEnterpriseContact.company_id == context.company_id,
        InternshipEnterpriseContact.is_deleted.is_(False),
    ))
    if not contact:
        raise AppException("VALIDATION_ERROR", "企业导师不存在或不属于当前企业")
    return int(contact.id)


def _validate_position_relations_in_tx(db, *, context, values: dict[str, Any]) -> None:
    if "mentor_contact_id" in values:
        values["mentor_contact_id"] = _validate_mentor_contact_in_tx(
            db, context=context, mentor_contact_id=values["mentor_contact_id"],
        )


def create_position_in_tx(db, *, context, payload: dict[str, Any]) -> dict:
    _assert_editor(context)
    _writable_campaign(db, context)
    values = _normalized_position_values(payload, creating=True)
    _validate_position_relations_in_tx(db, context=context, values=values)
    company = _company(db, context)
    row = InternshipPosition(
        tenant_id=context.tenant_id,
        company_id=context.company_id,
        company_name=company.name,
        campaign_id=context.campaign_id,
        batch_id=context.batch_id,
        source_type="ENTERPRISE",
        status="DRAFT",
        **values,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        context,
        target_type="POSITION",
        target_id=row.id,
        action="ENTERPRISE_POSITION_CREATE",
        detail={"campaignId": str(context.campaign_id)},
    )
    return _position_row(row)


def update_position_in_tx(db, *, context, position_id: int, payload: dict[str, Any]) -> dict:
    _assert_editor(context)
    _writable_campaign(db, context)
    if payload.get("expectedVersion") is None:
        raise AppException("DATA_CONFLICT", "编辑岗位必须携带当前版本")
    row = _position(db, context, position_id, lock=True)
    if row.status != "DRAFT":
        raise AppException("DATA_CONFLICT", "企业仅可编辑草稿岗位；待审岗位请先撤回")
    if int(row.version or 0) != int(payload["expectedVersion"]):
        raise AppException("DATA_CONFLICT", "岗位已更新，请刷新后重试")
    values = _normalized_position_values(payload, creating=False)
    _validate_position_relations_in_tx(db, context=context, values=values)
    if "headcount" in values and int(values["headcount"]) < int(row.allocated_count or 0):
        raise AppException("VALIDATION_ERROR", "招聘人数不能小于已正式落岗人数")
    for column, value in values.items():
        setattr(row, column, value)
    if not str(row.title or "").strip():
        raise AppException("VALIDATION_ERROR", "岗位名称必填")
    row.version = int(row.version or 0) + 1
    _audit(
        db,
        context,
        target_type="POSITION",
        target_id=row.id,
        action="ENTERPRISE_POSITION_UPDATE",
        detail={"version": int(row.version or 0)},
    )
    db.flush()
    return _position_row(row)


def _assert_submit_ready(row: InternshipPosition) -> None:
    missing = []
    if not str(row.title or "").strip():
        missing.append("岗位名称")
    if int(row.headcount or 0) <= 0:
        missing.append("招聘人数")
    if not str(row.work_content or "").strip():
        missing.append("工作内容")
    if not str(row.work_location or "").strip():
        missing.append("工作地点")
    if not str(row.work_address or "").strip():
        missing.append("详细地址")
    if row.weekly_hours is None or float(row.weekly_hours) <= 0:
        missing.append("每周工时")
    if not (str(row.salary_range or "").strip() or row.remuneration_amount is not None):
        missing.append("报酬条件")
    if missing:
        raise AppException("VALIDATION_ERROR", "提交学校审核前请完善：" + "、".join(missing))


def submit_position_in_tx(db, *, context, position_id: int, expected_version: int | None) -> dict:
    _assert_editor(context)
    campaign = _campaign(db, context, lock=True)
    assert_campaign_operation_window(campaign, "POSITION_SUBMIT")
    row = _position(db, context, position_id, lock=True)
    if row.status != "DRAFT":
        raise AppException("DATA_CONFLICT", "仅草稿岗位可提交学校审核")
    if expected_version is None or int(row.version or 0) != int(expected_version):
        raise AppException("DATA_CONFLICT", "岗位版本已变化，请刷新后重试")
    _assert_submit_ready(row)
    row.status = "PENDING"
    row.version = int(row.version or 0) + 1
    _audit(
        db,
        context,
        target_type="POSITION",
        target_id=row.id,
        action="ENTERPRISE_POSITION_SUBMIT",
        detail={"campaignId": str(context.campaign_id), "version": int(row.version or 0)},
    )
    db.flush()
    return _position_row(row)


def withdraw_position_in_tx(db, *, context, position_id: int, expected_version: int | None) -> dict:
    _assert_editor(context)
    _writable_campaign(db, context)
    row = _position(db, context, position_id, lock=True)
    if row.status != "PENDING":
        raise AppException("DATA_CONFLICT", "仅待学校审核岗位可撤回")
    if expected_version is None or int(row.version or 0) != int(expected_version):
        raise AppException("DATA_CONFLICT", "岗位版本已变化，请刷新后重试")
    row.status = "DRAFT"
    row.version = int(row.version or 0) + 1
    _audit(
        db,
        context,
        target_type="POSITION",
        target_id=row.id,
        action="ENTERPRISE_POSITION_WITHDRAW",
        detail={"campaignId": str(context.campaign_id), "version": int(row.version or 0)},
    )
    db.flush()
    return _position_row(row)


def dashboard_in_tx(db, *, context) -> dict:
    """Truthful recruitment metrics. Unsupported E9 metrics are omitted rather than fabricated."""
    from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc

    base = _position_query(context)
    published = int(db.scalar(select(func.count()).select_from(base.where(InternshipPosition.status == "PUBLISHED").subquery())) or 0)
    pending = int(db.scalar(select(func.count()).select_from(base.where(InternshipPosition.status == "PENDING").subquery())) or 0)
    _rows, applicants = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1)
    pending_applications, todo = decision_svc.list_owned_applications_in_tx(
        db, context=context, page=1, page_size=3, decision_status="PENDING")
    _rows, interview = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1, decision_status="INTERVIEW")
    _rows, accept_intent = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1, decision_status="ACCEPT_INTENT")
    tasks = []
    campaign = _campaign(db, context)
    writable = _role(context) in _EDITOR_ROLES and campaign.status == "OPEN"
    if writable:
        public_return = select(func.max(InternshipAuditTrail.id)).where(
            InternshipAuditTrail.tenant_id == context.tenant_id,
            InternshipAuditTrail.target_type == "POSITION",
            InternshipAuditTrail.target_id == InternshipPosition.id,
            InternshipAuditTrail.action == "STATUS_RETURN",
            InternshipAuditTrail.detail_json["enterpriseVisible"].as_boolean().is_(True),
        ).correlate(InternshipPosition).scalar_subquery()
        last_submission = select(func.max(InternshipAuditTrail.id)).where(
            InternshipAuditTrail.tenant_id == context.tenant_id,
            InternshipAuditTrail.target_type == "POSITION",
            InternshipAuditTrail.target_id == InternshipPosition.id,
            InternshipAuditTrail.action.in_(["STATUS_SUBMIT", "ENTERPRISE_POSITION_SUBMIT", "ENTERPRISE_POSITION_WITHDRAW"]),
        ).correlate(InternshipPosition).scalar_subquery()
        needs_correction = func.coalesce(public_return > func.coalesce(last_submission, 0), False)
        draft_rows = db.execute(base.add_columns(needs_correction).where(InternshipPosition.status == "DRAFT").order_by(
            needs_correction.desc(), InternshipPosition.updated_at.desc(), InternshipPosition.id.desc(),
        ).limit(3)).all()
        drafts = [position for position, _ in draft_rows]
        returns = school_returns_in_tx(db, context=context, position_ids=[p.id for p in drafts])
        for position, correction_pending in draft_rows:
            position_id = str(position.id)
            returned = returns.get(position.id) if correction_pending else None
            tasks.append({
                "key": f"position:{position_id}",
                "objectType": "INTERNSHIP_POSITION",
                "objectId": position_id,
                "title": f"{position.title} · {'待补正' if returned else '草稿待提交'}",
                "description": returned["reason"] if returned else "继续完善岗位资料，保存后提交学校审核。",
                "whyHere": "学校已退回该岗位，请按意见补充。" if returned else "该岗位尚未提交学校审核。",
                "recentChange": "学校已给出补正意见" if returned else f"岗位版本 v{int(position.version or 0)}",
                "waitingOn": "企业管理员或 HR 完善原岗位资料",
                "nextActor": "重新提交后由学校审核发布条件" if returned else "提交后由学校审核发布条件",
                "href": f"/positions/{position_id}/edit?campaignId={context.campaign_id}",
                "actionLabel": "补正这个岗位" if returned else "继续填写",
                "resumeKey": f"enterprise:position:{position_id}",
            })
    for application in pending_applications:
        application_id = str(application.get("applicationId") or "")
        student = dict(application.get("student") or {})
        student_name = student.get("realName") or "学生"
        position_title = application.get("positionTitle") or "申请岗位"
        submitted_at = application.get("submittedAt") or "提交时间待核对"
        tasks.append({
            "key": f"application:{application_id}",
            "objectType": "INTERNSHIP_APPLICATION",
            "objectId": application_id,
            "title": f"{student_name} · {position_title}",
            "description": f"第 {int(application.get('volunteerNo') or 0)} 志愿，仍等待企业处理。",
            "whyHere": "该报名属于当前企业与招聘季，企业决定尚未形成。",
            "recentChange": f"学生提交于 {submitted_at}",
            "waitingOn": "等待企业管理员或 HR 核对材料并作出企业决定",
            "nextActor": "如选择拟接收，下一步仍由学校最终确认正式落岗",
            "href": f"/applications/{application_id}",
            "actionLabel": "处理这份报名",
            "resumeKey": f"enterprise:application:{application_id}",
        })
    pending_positions = db.scalars(
        base.where(InternshipPosition.status == "PENDING").order_by(
            InternshipPosition.updated_at.desc(), InternshipPosition.id.desc()).limit(2)
    ).all()
    for position in pending_positions:
        position_id = str(position.id)
        tasks.append({
            "key": f"position:{position_id}",
            "objectType": "INTERNSHIP_POSITION",
            "objectId": position_id,
            "title": f"{position.title} · 待学校审核",
            "description": "岗位已提交，当前不可直接编辑；确需修改时可从详情撤回到草稿。",
            "whyHere": "学校尚未完成岗位发布审核。",
            "recentChange": f"岗位版本 v{int(position.version or 0)}",
            "waitingOn": "等待学校审核岗位发布条件",
            "nextActor": "学校通过后岗位才会进入学生可见的正式岗位库",
            "href": f"/positions/{position_id}/edit",
            "actionLabel": "查看这个岗位",
            "resumeKey": f"enterprise:position:{position_id}",
        })
    return {
        "metrics": {
            "published": published,
            "pending": pending,
            "applicants": int(applicants),
            "todoApplicants": int(todo),
            "interview": int(interview),
            "acceptIntent": int(accept_intent),
        },
        "tasks": tasks,
    }
