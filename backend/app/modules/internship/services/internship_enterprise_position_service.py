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


def _campaign(db, context) -> InternshipRecruitmentCampaign:
    row = db.scalar(
        select(InternshipRecruitmentCampaign).where(
            InternshipRecruitmentCampaign.id == context.campaign_id,
            InternshipRecruitmentCampaign.tenant_id == context.tenant_id,
            InternshipRecruitmentCampaign.is_deleted.is_(False),
        )
    )
    if not row:
        raise not_found("招聘季不存在或不在当前企业上下文")
    return row


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
    return [_campaign_row(campaign, participation.status) for participation, campaign in rows]


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


def get_position_in_tx(db, *, context, position_id: int) -> dict:
    return _position_row(_position(db, context, position_id))


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
    campaign = _campaign(db, context)
    if str(campaign.status or "").upper() in {"CLOSED", "ARCHIVED"}:
        raise AppException("DATA_CONFLICT", "招聘季已关闭，不能新建岗位")
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
    campaign = _campaign(db, context)
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
    campaign = _campaign(db, context)
    if str(campaign.status or "").upper() != "OPEN":
        raise AppException("DATA_CONFLICT", "招聘季当前状态不允许撤回岗位")
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
    _rows, todo = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1, decision_status="PENDING")
    _rows, interview = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1, decision_status="INTERVIEW")
    _rows, accept_intent = decision_svc.list_owned_applications_in_tx(db, context=context, page=1, page_size=1, decision_status="ACCEPT_INTENT")
    tasks = []
    if pending:
        tasks.append({"key": "pending-positions", "title": f"{pending} 个岗位等待学校审核", "description": "待审核岗位不可继续编辑；如需修改先撤回到草稿。", "href": "/positions", "actionLabel": "查看岗位"})
    if todo:
        tasks.append({"key": "pending-applications", "title": f"{todo} 份报名申请待处理", "description": "仅企业管理员/HR可处理，所有决定继续由服务端校验招聘季和企业范围。", "href": "/applicants", "actionLabel": "处理报名"})
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
