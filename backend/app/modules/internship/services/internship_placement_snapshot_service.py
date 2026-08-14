"""Build and insert immutable placement evidence inside the caller's canonical assignment transaction."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from sqlalchemy import func, select

from app.core.context import get_current_user
from app.core.exceptions import AppException
from app.models import EmpCompany, InternshipPosition
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_sha256(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _captured_by_user_id() -> int | None:
    user = get_current_user() or {}
    value = str(user.get("userId") or "")
    if value.startswith("db-"):
        value = value[3:]
    try:
        return int(value) if value else None
    except ValueError:
        return None


def capture_placement_snapshot_in_tx(
    db,
    *,
    record,
    position: InternshipPosition,
    company: EmpCompany,
    rights: dict,
    source_application_id: int | None = None,
    source_enterprise_decision_id: int | None = None,
) -> InternshipPlacementSnapshot:
    """Caller already holds record/position locks; any failure must abort the caller transaction."""
    if not record.batch_id:
        raise AppException("DATA_CONFLICT", "正式落岗缺少实习批次，不能生成历史快照")
    current_max = db.scalar(
        select(func.max(InternshipPlacementSnapshot.placement_seq)).where(
            InternshipPlacementSnapshot.tenant_id == record.tenant_id,
            InternshipPlacementSnapshot.record_id == record.id,
        )
    )
    placement_seq = int(current_max or 0) + 1
    captured_at = datetime.utcnow()
    payload = {
        "recordId": str(record.id),
        "placementSeq": placement_seq,
        "applicationId": str(source_application_id) if source_application_id else None,
        "enterpriseDecisionId": str(source_enterprise_decision_id) if source_enterprise_decision_id else None,
        "campaignId": str(position.campaign_id) if position.campaign_id else None,
        "batchId": str(record.batch_id),
        "companyId": str(company.id),
        "positionId": str(position.id),
        "companyName": company.name,
        "companyCreditCode": company.credit_code,
        "positionTitle": position.title,
        "positionCategory": position.category,
        "workLocation": position.work_location,
        "workAddress": position.work_address,
        "workContent": position.work_content,
        "majorRequirement": position.major_requirement,
        "gradeRequirement": position.grade_requirement,
        "salaryRange": position.salary_range,
        "subsidy": position.subsidy,
        "remunerationType": position.remuneration_type,
        "remunerationAmount": position.remuneration_amount,
        "remunerationCycle": position.remuneration_cycle,
        "dailyHours": position.daily_hours,
        "weeklyHours": position.weekly_hours,
        "shiftType": position.shift_type,
        "nightShift": position.night_shift,
        "overtimeAllowed": position.overtime_allowed,
        "restDays": position.rest_days,
        "restDaysPerWeek": position.rest_days_per_week,
        "accommodationProvided": position.accommodation_provided,
        "mealProvided": position.meal_provided,
        "hazardousFlag": position.hazardous_flag,
        "specialEquipment": position.special_equipment,
        "prohibitedReason": position.prohibited_reason,
        "enterpriseMentorName": position.mentor_name,
        "rightsStatus": position.rights_status,
        "rightsRuleVersion": position.rights_rule_version,
        "rightsCheckedAt": position.rights_checked_at.isoformat() if position.rights_checked_at else None,
        "positionVersion": int(position.version or 0),
        "positionUpdatedAt": position.updated_at.isoformat() if position.updated_at else None,
        "rightsEvaluation": {
            "passed": bool(rights.get("passed")),
            "ruleVersion": rights.get("ruleVersion") or position.rights_rule_version,
        },
        "capturedAt": captured_at.isoformat(),
    }
    digest = snapshot_sha256(payload)
    row = InternshipPlacementSnapshot(
        tenant_id=record.tenant_id,
        record_id=record.id,
        placement_seq=placement_seq,
        application_id=source_application_id,
        enterprise_decision_id=source_enterprise_decision_id,
        campaign_id=position.campaign_id,
        batch_id=record.batch_id,
        company_id=company.id,
        position_id=position.id,
        company_name=company.name,
        company_credit_code=company.credit_code,
        position_title=position.title,
        position_category=position.category,
        work_location=position.work_location,
        work_address=position.work_address,
        work_content=position.work_content,
        major_requirement=position.major_requirement,
        grade_requirement=position.grade_requirement,
        salary_range=position.salary_range,
        subsidy=position.subsidy,
        remuneration_type=position.remuneration_type,
        remuneration_amount=position.remuneration_amount,
        remuneration_cycle=position.remuneration_cycle,
        daily_hours=position.daily_hours,
        weekly_hours=position.weekly_hours,
        shift_type=position.shift_type,
        night_shift=position.night_shift,
        overtime_allowed=position.overtime_allowed,
        rest_days=position.rest_days,
        rest_days_per_week=position.rest_days_per_week,
        accommodation_provided=position.accommodation_provided,
        meal_provided=position.meal_provided,
        hazardous_flag=position.hazardous_flag,
        special_equipment=position.special_equipment,
        prohibited_reason=position.prohibited_reason,
        enterprise_mentor_name=position.mentor_name,
        rights_status=position.rights_status,
        rights_rule_version=position.rights_rule_version,
        rights_checked_at=position.rights_checked_at,
        position_version=int(position.version or 0),
        position_updated_at=position.updated_at,
        snapshot_json=payload,
        snapshot_sha256=digest,
        captured_at=captured_at,
        captured_by_user_id=_captured_by_user_id(),
    )
    db.add(row)
    db.flush()
    record.current_placement_snapshot_id = row.id
    return row
