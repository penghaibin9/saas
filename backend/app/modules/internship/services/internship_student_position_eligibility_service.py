"""Catalog and volunteer submission share one canonical eligibility guard."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, false, func, literal, or_, select

from app.core.exceptions import AppException, not_found
from app.models import (
    EmpCompany,
    InternshipBatch,
    InternshipBatchParticipant,
    InternshipEnterpriseInspection,
    InternshipPosition,
    StudentProfile,
)
from app.models.internship_enterprise_portal import InternshipCampaignEnterprise, InternshipRecruitmentCampaign
from app.modules.internship.services import internship_recruitment_window_guard as window_guard
from app.modules.internship.services.internship_compliance_rules import get_batch_compliance_rules
from app.modules.internship.services.internship_position_rights import evaluate_position_publishability

# Python str.strip() uses Unicode whitespace semantics, while MySQL TRIM(expr) removes ordinary
# spaces only. ICU regex (MySQL 8) supplies the portable SQL projection; the explicit code points
# cover Python's additional C0 separators and Unicode White_Space edge cases as well.
_PYTHON_STRIP_EDGE_WS_REGEX = (
    r"^[[:space:]\x{001C}-\x{001F}\x{0085}\x{00A0}\x{1680}\x{2000}-\x{200A}"
    r"\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}]+|"
    r"[[:space:]\x{001C}-\x{001F}\x{0085}\x{00A0}\x{1680}\x{2000}-\x{200A}"
    r"\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}]+$"
)


def _python_strip_sql(value):
    """Project Python ``str.strip()`` edge-whitespace semantics into MySQL 8 SQL."""
    return func.regexp_replace(value, _PYTHON_STRIP_EDGE_WS_REGEX, "")


def assert_student_selection_window(campaign: InternshipRecruitmentCampaign, now: datetime | None = None) -> None:
    window_guard.assert_campaign_operation_window(campaign, "STUDENT_SELECT", now=now)


def _major_sql_predicate(major_name: str):
    """MySQL SQL equivalent of `_major_hit`, including Python strip/case/accent semantics."""
    major = str(major_name or "").strip()
    requirement = InternshipPosition.major_requirement
    normalized_requirement = _python_strip_sql(requirement)
    unlimited = or_(requirement.is_(None), func.length(normalized_requirement) == 0)
    if not major:
        return unlimited

    # Production columns use utf8mb4_unicode_ci, while Python's `_major_hit` strips Unicode edge
    # whitespace and then uses case/accent-sensitive `in`. Normalize first, then force binary
    # collation so COUNT/page filtering and public-row classification stay equivalent.
    binary_requirement = normalized_requirement.collate("utf8mb4_bin")
    binary_major = literal(major).collate("utf8mb4_bin")
    return or_(
        unlimited,
        func.locate(binary_major, binary_requirement) > 0,
        func.locate(binary_requirement, binary_major) > 0,
    )


def _latest_approved_inspection_predicates(*, tenant_id: int, current: datetime):
    """Mirror is_enterprise_access_valid's latest APPROVED inspection semantics in SQL."""
    latest_approved_id = (
        select(func.max(InternshipEnterpriseInspection.id))
        .where(
            InternshipEnterpriseInspection.tenant_id == tenant_id,
            InternshipEnterpriseInspection.company_id == EmpCompany.id,
            InternshipEnterpriseInspection.status == "APPROVED",
            InternshipEnterpriseInspection.is_deleted.is_(False),
        )
        .correlate(EmpCompany)
        .scalar_subquery()
    )
    latest_valid_until = (
        select(InternshipEnterpriseInspection.valid_until)
        .where(
            InternshipEnterpriseInspection.id == latest_approved_id,
            InternshipEnterpriseInspection.tenant_id == tenant_id,
            InternshipEnterpriseInspection.is_deleted.is_(False),
        )
        .scalar_subquery()
    )
    return latest_approved_id.is_not(None), or_(latest_valid_until.is_(None), latest_valid_until >= current)


def apply_catalog_query_eligibility_filters_in_tx(
    db,
    query,
    *,
    tenant_id: int,
    record,
    campaign,
    major_name: str = "",
    only_major_matched: bool = False,
    now: datetime | None = None,
):
    """Push the canonical APPLY hard predicates into SQL before COUNT/OFFSET/LIMIT.

    This is a query projection of `evaluate_position_for_student_in_tx`, not a replacement for it.
    The paged rows are still re-evaluated by the canonical guard before being returned. Keeping the
    SQL projection here beside that guard prevents catalog pagination from defining pages over rows
    that are subsequently dropped, while bounding the expensive evaluator to at most `pageSize`.
    """
    current = now or datetime.utcnow()
    try:
        assert_student_selection_window(campaign, current)
    except AppException:
        return query.where(false())
    if (
        record.tenant_id != tenant_id
        or record.batch_id != campaign.batch_id
        or record.status not in {"PREPARING", "READY"}
        or record.eligibility_status != "QUALIFIED"
        or record.position_id
        or record.destination_type in {"ASSIGNED", "SELF_ARRANGED"}
    ):
        return query.where(false())

    participant = db.scalar(select(InternshipBatchParticipant.id).where(
        InternshipBatchParticipant.tenant_id == tenant_id,
        InternshipBatchParticipant.batch_id == campaign.batch_id,
        InternshipBatchParticipant.student_id == record.student_id,
        InternshipBatchParticipant.status == "ACTIVE",
        InternshipBatchParticipant.is_deleted.is_(False),
    ))
    if not participant:
        return query.where(false())

    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id,
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    ))
    batch = db.scalar(select(InternshipBatch).where(
        InternshipBatch.id == campaign.batch_id,
        InternshipBatch.tenant_id == tenant_id,
        InternshipBatch.is_deleted.is_(False),
    ))
    if not student or not batch:
        return query.where(false())

    rules = get_batch_compliance_rules(db, batch)
    rights_cfg = dict(rules.get("workRights") or {})
    try:
        max_daily = float(rights_cfg.get("maxDailyHours", 8))
        max_weekly = float(rights_cfg.get("maxWeeklyHours", 40))
    except (TypeError, ValueError):
        # Canonical evaluator would not be able to establish a safe limit either.
        return query.where(false())

    normalized_work_content = _python_strip_sql(InternshipPosition.work_content)
    normalized_remuneration_type = _python_strip_sql(InternshipPosition.remuneration_type)
    unpaid_exact = and_(
        func.char_length(InternshipPosition.remuneration_type) == len("UNPAID"),
        InternshipPosition.remuneration_type.collate("utf8mb4_bin")
        == literal("UNPAID").collate("utf8mb4_bin"),
    )
    query = query.where(
        func.length(normalized_work_content) > 0,
        InternshipPosition.daily_hours.is_not(None),
        InternshipPosition.daily_hours <= max_daily,
        InternshipPosition.weekly_hours.is_not(None),
        InternshipPosition.weekly_hours <= max_weekly,
        InternshipPosition.night_shift.is_not(None),
        InternshipPosition.overtime_allowed.is_not(None),
        InternshipPosition.rest_days_per_week.is_not(None),
        InternshipPosition.remuneration_type.is_not(None),
        func.length(normalized_remuneration_type) > 0,
        InternshipPosition.accommodation_provided.is_not(None),
        InternshipPosition.meal_provided.is_not(None),
        InternshipPosition.hazardous_flag.is_(False),
        # Python treats every non-empty string, including ordinary/Unicode whitespace, as truthy.
        # Use character length instead of an equality under MySQL PAD SPACE collation.
        or_(
            InternshipPosition.prohibited_reason.is_(None),
            func.char_length(InternshipPosition.prohibited_reason) == 0,
        ),
        or_(
            unpaid_exact,
            and_(
                InternshipPosition.remuneration_amount.is_not(None),
                InternshipPosition.remuneration_cycle.is_not(None),
                # Canonical Python uses truthiness here, so a whitespace-only but non-empty cycle is
                # still truthy. char_length preserves that exact behavior; `!= ''` under PAD SPACE
                # would incorrectly exclude ordinary spaces.
                func.char_length(InternshipPosition.remuneration_cycle) > 0,
            ),
        ),
        # Canonical evaluate_position_for_student_in_tx enforces the company master expiry before
        # rights-layer options. Keep it unconditional here as well so exact total/page semantics do
        # not depend on workRights.requireEnterpriseAccess.
        or_(
            EmpCompany.access_valid_until.is_(None),
            EmpCompany.access_valid_until >= current,
        ),
    )

    # Student-specific APPLY blockers that do not exist at school-side PUBLISH time.
    birth = getattr(student, "birth_date", None)
    is_minor = False
    if birth is not None:
        if hasattr(birth, "date"):
            birth = birth.date()
        try:
            today = current.date()
            years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            is_minor = years < 18
        except Exception:
            is_minor = False
    if not rights_cfg.get("nightShiftAllowed", False) or is_minor:
        query = query.where(InternshipPosition.night_shift.is_(False))
    if not rights_cfg.get("overtimeAllowed", False):
        query = query.where(InternshipPosition.overtime_allowed.is_(False))

    # evaluate_position_publishability defaults this extra inspection/access guard to ON when the
    # key is omitted. Company master expiry above remains unconditional regardless of this option.
    if rights_cfg.get("requireEnterpriseAccess", True):
        access_cfg = dict(rules.get("enterpriseAccess") or {})
        if access_cfg.get("required") or access_cfg.get("requireOnsiteInspection"):
            query = query.where(*_latest_approved_inspection_predicates(
                tenant_id=tenant_id, current=current,
            ))

    if only_major_matched:
        query = query.where(_major_sql_predicate(major_name))
    return query


def evaluate_position_for_student_in_tx(
    db,
    *,
    tenant_id: int,
    record,
    campaign,
    position: InternshipPosition,
    now=None,
) -> dict:
    current = now or datetime.utcnow()
    assert_student_selection_window(campaign, current)
    if record.tenant_id != tenant_id or record.batch_id != campaign.batch_id:
        raise AppException("DATA_CONFLICT", "学生实习记录与招聘季不一致")
    if record.status not in {"PREPARING", "READY"}:
        raise AppException("DATA_CONFLICT", "当前实习状态不可参与招聘季选岗")
    if record.eligibility_status != "QUALIFIED":
        raise AppException("NO_PERMISSION", "学生实习资格尚未通过")
    if record.position_id or record.destination_type in {"ASSIGNED", "SELF_ARRANGED"}:
        raise AppException("DATA_CONFLICT", "学生实习去向已落实")

    participant = db.scalar(select(InternshipBatchParticipant).where(
        InternshipBatchParticipant.tenant_id == tenant_id,
        InternshipBatchParticipant.batch_id == campaign.batch_id,
        InternshipBatchParticipant.student_id == record.student_id,
        InternshipBatchParticipant.status == "ACTIVE",
        InternshipBatchParticipant.is_deleted.is_(False),
    ))
    if not participant:
        raise AppException("NO_PERMISSION", "学生不在当前批次正式参与名单")

    if (
        position.tenant_id != tenant_id
        or position.batch_id != campaign.batch_id
        or position.campaign_id != campaign.id
    ):
        raise not_found("岗位不属于当前招聘季/批次")
    if position.status != "PUBLISHED" or int(position.allocated_count or 0) >= int(position.headcount or 0):
        raise AppException("DATA_CONFLICT", "岗位未发布、已下架或已满员")

    company = db.scalar(select(EmpCompany).where(
        EmpCompany.id == position.company_id,
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    ))
    if not company:
        raise not_found("岗位企业不存在或不在当前租户")
    if (company.status or "").upper() != "ACTIVE":
        raise AppException("NO_PERMISSION", "岗位企业主档已停用")
    if company.blacklist or company.coop_status == "BLACKLIST":
        raise AppException("NO_PERMISSION", "黑名单企业不可参与招聘")
    if company.coop_status != "ACTIVE" or company.qualification_status != "PASSED":
        raise AppException("NO_PERMISSION", "企业合作或资质状态未通过")
    if company.access_valid_until and company.access_valid_until < current:
        raise AppException("NO_PERMISSION", "企业准入已过期")

    accepted = db.scalar(select(InternshipCampaignEnterprise.id).where(
        InternshipCampaignEnterprise.tenant_id == tenant_id,
        InternshipCampaignEnterprise.campaign_id == campaign.id,
        InternshipCampaignEnterprise.company_id == company.id,
        InternshipCampaignEnterprise.status == "ACCEPTED",
        InternshipCampaignEnterprise.is_deleted.is_(False),
    ))
    if not accepted:
        raise AppException("NO_PERMISSION", "企业未接受当前招聘季邀请")

    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == record.student_id,
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    ))
    batch = db.scalar(select(InternshipBatch).where(
        InternshipBatch.id == campaign.batch_id,
        InternshipBatch.tenant_id == tenant_id,
        InternshipBatch.is_deleted.is_(False),
    ))
    if not student or not batch:
        raise AppException("DATA_CONFLICT", "学生主档或实习批次不存在")

    rights = evaluate_position_publishability(
        position, company, batch, student, operation="APPLY", db=db,
    )
    if not rights.get("passed"):
        raise AppException(
            "DATA_CONFLICT",
            "岗位劳动权益/准入校验未通过",
            details={
                "blockers": rights.get("blockers", []),
                "unknowns": rights.get("unknowns", []),
            },
        )
    return {
        "eligible": True,
        "position": position,
        "company": company,
        "rights": rights,
        "majorMatchHardBlock": False,
    }
