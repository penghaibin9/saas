"""Student catalog read facade over canonical recruitment/eligibility Authorities."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import EmpCompany, InternshipPosition, Major, StudentProfile
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_student_position_eligibility_service as eligibility_svc
from app.modules.internship.services import internship_student_profile_service as profile_svc
from app.modules.internship.services import internship_student_selection_service as selection_svc
from app.services.db_service import _as_id, _iso, _tid, session

_ACTIVE_GROUP_STATUSES = ("DRAFT", "SUBMITTED", "LOCKED", "NEEDS_REVISION", "APPROVED")


def _escape_like(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _true_filter(value) -> bool:
    if value is True:
        return True
    if value in (None, "", False):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _major_hit(major_name: str, requirement: str) -> bool:
    major = str(major_name or "").strip()
    required = str(requirement or "").strip()
    if not required:
        return True
    if not major:
        return False
    return major in required or required in major


def _student_major_name(db, *, tenant_id: int, student_id: int) -> str:
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == student_id,
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    ))
    if not student or not student.major_id:
        return ""
    major = db.scalar(select(Major).where(
        Major.id == student.major_id,
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ))
    return str(major.major_name or "").strip() if major else ""


def _selection_state(campaign, record) -> tuple[bool, str]:
    try:
        eligibility_svc.assert_student_selection_window(campaign)
    except AppException as exc:
        return False, str(getattr(exc, "message", None) or "当前招聘季不在学生选岗时间窗")
    if str(record.status or "").upper() not in {"PREPARING", "READY"}:
        return False, "当前实习状态不可参与招聘季选岗"
    if str(record.eligibility_status or "").upper() != "QUALIFIED":
        return False, "学生实习资格尚未通过"
    if record.position_id or str(record.destination_type or "").upper() in {"ASSIGNED", "SELF_ARRANGED"}:
        return False, "学生实习去向已落实"
    return True, ""


def _base_query(*, tenant_id: int, campaign):
    return (
        select(InternshipPosition, EmpCompany)
        .join(EmpCompany, and_(
            EmpCompany.id == InternshipPosition.company_id,
            EmpCompany.tenant_id == InternshipPosition.tenant_id,
        ))
        .join(InternshipCampaignEnterprise, and_(
            InternshipCampaignEnterprise.tenant_id == InternshipPosition.tenant_id,
            InternshipCampaignEnterprise.campaign_id == InternshipPosition.campaign_id,
            InternshipCampaignEnterprise.company_id == InternshipPosition.company_id,
        ))
        .where(
            InternshipPosition.tenant_id == tenant_id,
            InternshipPosition.batch_id == campaign.batch_id,
            InternshipPosition.campaign_id == campaign.id,
            InternshipPosition.status == "PUBLISHED",
            InternshipPosition.allocated_count < InternshipPosition.headcount,
            InternshipPosition.is_deleted.is_(False),
            EmpCompany.tenant_id == tenant_id,
            EmpCompany.status == "ACTIVE",
            EmpCompany.coop_status == "ACTIVE",
            EmpCompany.qualification_status == "PASSED",
            EmpCompany.blacklist.is_(False),
            EmpCompany.is_deleted.is_(False),
            InternshipCampaignEnterprise.status == "ACCEPTED",
            InternshipCampaignEnterprise.is_deleted.is_(False),
        )
    )


def _filtered(q, params: dict):
    keyword = str(params.get("keyword") or "").strip()
    for token in [part for part in keyword.split() if part]:
        pattern = f"%{_escape_like(token)}%"
        q = q.where(or_(
            InternshipPosition.title.like(pattern, escape="\\"),
            InternshipPosition.company_name.like(pattern, escape="\\"),
            InternshipPosition.category.like(pattern, escape="\\"),
            InternshipPosition.work_location.like(pattern, escape="\\"),
            InternshipPosition.work_address.like(pattern, escape="\\"),
            InternshipPosition.major_requirement.like(pattern, escape="\\"),
            EmpCompany.name.like(pattern, escape="\\"),
            EmpCompany.industry.like(pattern, escape="\\"),
            EmpCompany.city.like(pattern, escape="\\"),
        ))
    city = str(params.get("city") or "").strip()
    if city:
        pattern = f"%{_escape_like(city)}%"
        q = q.where(or_(EmpCompany.city.like(pattern, escape="\\"), InternshipPosition.work_location.like(pattern, escape="\\")))
    company_filter = str(params.get("companyId") or "").strip()
    if company_filter:
        if company_filter.isdigit():
            q = q.where(InternshipPosition.company_id == _as_id(company_filter))
        else:
            pattern = f"%{_escape_like(company_filter)}%"
            q = q.where(EmpCompany.name.like(pattern, escape="\\"))
    for key, column in (("accommodation", InternshipPosition.accommodation_provided), ("meal", InternshipPosition.meal_provided), ("nightShift", InternshipPosition.night_shift)):
        if params.get(key) not in (None, ""):
            q = q.where(column.is_(bool(params[key])))
    if str(params.get("industry") or "").strip():
        q = q.where(EmpCompany.industry == str(params["industry"]).strip())
    if str(params.get("scale") or "").strip():
        q = q.where(EmpCompany.scale == str(params["scale"]).strip())
    if params.get("weeklyHours") not in (None, ""):
        q = q.where(InternshipPosition.weekly_hours <= float(params["weeklyHours"]))
    if params.get("remaining") not in (None, ""):
        q = q.where((InternshipPosition.headcount - InternshipPosition.allocated_count) >= int(params["remaining"]))
    if params.get("remuneration") not in (None, ""):
        q = q.where(InternshipPosition.remuneration_amount >= float(params["remuneration"]))
    published_from = str(params.get("publishedFrom") or "").strip()
    if published_from:
        try:
            q = q.where(InternshipPosition.publish_at >= datetime.fromisoformat(published_from))
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "publishedFrom 必须是 ISO-8601 日期时间") from exc
    return q


def _public_row(position: InternshipPosition, company: EmpCompany, verdict: dict, *, major_matched: bool) -> dict:
    remaining = max(0, int(position.headcount or 0) - int(position.allocated_count or 0))
    requirement = str(position.major_requirement or "").strip()
    match_state = "UNLIMITED" if not requirement else ("MATCHED" if major_matched else "POSSIBLE_MISMATCH")
    return {
        "id": str(position.id), "positionId": str(position.id), "campaignId": str(position.campaign_id or ""),
        "companyId": str(company.id), "companyName": company.name, "companyVerified": True, "schoolVerified": True,
        "title": position.title, "category": position.category or "", "workLocation": position.work_location or company.city or "",
        "address": position.work_address or company.address or "", "city": company.city or "",
        "majorRequirement": position.major_requirement or "", "requirements": position.major_requirement or "",
        "description": position.work_content or "", "headcount": int(position.headcount or 0),
        "allocatedCount": int(position.allocated_count or 0), "remaining": remaining,
        "salaryRange": position.salary_range or "",
        "remunerationDisplay": position.salary_range or (str(position.remuneration_amount) if position.remuneration_amount is not None else ""),
        "remunerationAmount": position.remuneration_amount, "subsidy": position.subsidy or "",
        "dailyHours": position.daily_hours, "weeklyHours": position.weekly_hours, "shiftType": position.shift_type or "",
        "nightShift": position.night_shift, "overtime": position.overtime_allowed, "restDays": position.rest_days or "",
        "accommodationProvided": position.accommodation_provided, "mealProvided": position.meal_provided,
        "hazardous": position.hazardous_flag, "equipment": position.special_equipment or "",
        "publishedAt": _iso(position.publish_at),
        "matchState": match_state,
        "industry": company.industry or "", "companyNature": company.nature or "", "companyScale": company.scale or "",
        "companyIntro": company.short_intro or "", "rights": dict(verdict.get("rights") or {}),
    }


def _eligible_rows(
    db,
    *,
    tenant_id: int,
    campaign,
    record,
    q,
    major_name: str = "",
    strict: bool = False,
) -> list[dict]:
    result: list[dict] = []
    for position, company in db.execute(q).all():
        try:
            verdict = eligibility_svc.evaluate_position_for_student_in_tx(
                db, tenant_id=tenant_id, record=record, campaign=campaign, position=position,
            )
        except AppException:
            if strict:
                # SQL eligibility projection and canonical guard diverged or a concurrent fact moved.
                # Fail closed instead of silently dropping a post-pagination row and corrupting page
                # boundaries/total semantics.
                raise
            continue
        major_matched = _major_hit(major_name, position.major_requirement or "")
        result.append(_public_row(position, company, verdict, major_matched=major_matched))
    return result


def _candidate_stats_in_tx(db, *, tenant_id: int, campaign, record) -> tuple[int, int]:
    """Count the same SQL-projected eligible set used by catalog pagination."""
    q = eligibility_svc.apply_catalog_query_eligibility_filters_in_tx(
        db,
        _base_query(tenant_id=tenant_id, campaign=campaign),
        tenant_id=tenant_id,
        record=record,
        campaign=campaign,
    )
    candidate = q.order_by(None).subquery()
    published = int(db.scalar(select(func.count()).select_from(candidate)) or 0)
    partners = int(db.scalar(select(func.count(func.distinct(candidate.c.company_id)))) or 0)
    return published, partners


def get_catalog_context(*, user: dict) -> dict:
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        can_select, reason = _selection_state(campaign, record)
        published, partners = _candidate_stats_in_tx(
            db, tenant_id=tenant_id, campaign=campaign, record=record,
        ) if can_select else (0, 0)
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id == tenant_id,
            InternshipVolunteerGroup.student_id == student_id,
            InternshipVolunteerGroup.record_id == record.id,
            InternshipVolunteerGroup.campaign_id == campaign.id,
            InternshipVolunteerGroup.status.in_(_ACTIVE_GROUP_STATUSES),
            InternshipVolunteerGroup.is_deleted.is_(False),
        ).order_by(InternshipVolunteerGroup.id.desc()))
        return {
            "campaignId": str(campaign.id), "campaignName": campaign.campaign_name, "campaignStatus": campaign.status,
            "campaign": {"id": str(campaign.id), "name": campaign.campaign_name, "status": campaign.status, "studentSelectionEndAt": _iso(campaign.student_select_end_at)},
            "studentSelectionEndAt": _iso(campaign.student_select_end_at), "canSelect": bool(can_select), "selectionBlockReason": reason,
            "stats": {"publishedPositions": published, "partnerCompanies": partners},
            "volunteerGroup": {"status": group.status if group else "DRAFT", "selectedCount": 0},
        }


def list_catalog_positions(*, user: dict, params: dict) -> dict:
    tenant_id = _tid()
    student_id = profile_svc.resolve_my_student_id(user)
    page = max(1, int(params.get("page") or 1)); page_size = min(100, max(1, int(params.get("pageSize") or 20)))
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        can_select, reason = _selection_state(campaign, record)
        if not can_select:
            return {"items": [], "total": 0, "page": page, "pageSize": page_size, "blockReason": reason}

        major_name = _student_major_name(db, tenant_id=tenant_id, student_id=student_id)
        q = _filtered(_base_query(tenant_id=tenant_id, campaign=campaign), params)
        q = eligibility_svc.apply_catalog_query_eligibility_filters_in_tx(
            db,
            q,
            tenant_id=tenant_id,
            record=record,
            campaign=campaign,
            major_name=major_name,
            only_major_matched=_true_filter(params.get("majorMatched")),
        )
        sort = str(params.get("sort") or "RECOMMENDED").upper()
        if sort == "LATEST": q = q.order_by(InternshipPosition.publish_at.desc(), InternshipPosition.id.desc())
        elif sort == "REMUNERATION": q = q.order_by(InternshipPosition.remuneration_amount.desc(), InternshipPosition.id.desc())
        elif sort == "REMAINING": q = q.order_by((InternshipPosition.headcount - InternshipPosition.allocated_count).desc(), InternshipPosition.id.desc())
        else: q = q.order_by(InternshipPosition.id.desc())

        # Pages and total are defined over the SQL projection of the canonical APPLY predicate.
        # The expensive canonical evaluator is therefore bounded to the selected page and may only
        # fail closed; it never silently discards rows after page boundaries have been fixed.
        total = int(db.scalar(select(func.count()).select_from(q.order_by(None).subquery())) or 0)
        page_q = q.offset((page - 1) * page_size).limit(page_size)
        rows = _eligible_rows(
            db,
            tenant_id=tenant_id,
            campaign=campaign,
            record=record,
            q=page_q,
            major_name=major_name,
            strict=True,
        )
        return {"items": rows, "total": total, "page": page, "pageSize": page_size}


def get_catalog_position(*, user: dict, position_id: int) -> dict:
    tenant_id = _tid(); student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        row = db.execute(_base_query(tenant_id=tenant_id, campaign=campaign).where(InternshipPosition.id == _as_id(position_id))).first()
        if not row: raise not_found("岗位不存在、未发布或不属于当前招聘季")
        position, company = row
        verdict = eligibility_svc.evaluate_position_for_student_in_tx(db, tenant_id=tenant_id, record=record, campaign=campaign, position=position)
        major_name = _student_major_name(db, tenant_id=tenant_id, student_id=student_id)
        return _public_row(position, company, verdict, major_matched=_major_hit(major_name, position.major_requirement or ""))


def get_catalog_company(*, user: dict, company_id: int) -> dict:
    tenant_id = _tid(); student_id = profile_svc.resolve_my_student_id(user)
    with session() as db:
        campaign, record = selection_svc._resolve_context_in_tx(db, tenant_id=tenant_id, student_id=student_id)
        major_name = _student_major_name(db, tenant_id=tenant_id, student_id=student_id)
        rows = _eligible_rows(
            db,
            tenant_id=tenant_id,
            campaign=campaign,
            record=record,
            q=_base_query(tenant_id=tenant_id, campaign=campaign).where(InternshipPosition.company_id == _as_id(company_id)),
            major_name=major_name,
        )
        if not rows: raise not_found("企业当前没有学生可选的已发布岗位")
        company = db.scalar(select(EmpCompany).where(EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == tenant_id, EmpCompany.is_deleted.is_(False)))
        if not company: raise not_found("企业不存在或不在当前可选范围")
        return {
            "id": str(company.id), "companyId": str(company.id), "logo": "", "name": company.name,
            "industry": company.industry or "", "nature": company.nature or "", "scale": company.scale or "",
            "city": company.city or "", "region": company.region or "", "shortIntro": company.short_intro or "",
            "mainBusiness": company.main_business or "", "website": company.website or "", "internCount": int(company.intern_count or 0),
            "activeJobs": len(rows), "schoolVerified": True,
        }
