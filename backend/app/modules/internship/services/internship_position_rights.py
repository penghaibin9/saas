"""岗位劳动权益唯一事实评估器。发布、分配和学生全过程评估必须复用。"""
from __future__ import annotations

from datetime import datetime

from app.modules.internship.services.internship_compliance_rules import (
    get_batch_compliance_rules, rule_version_label,
)


def _fact(position, name):
    return getattr(position, name, None) if position is not None else None


def _issue(code, label, reason, *, severity="BLOCK", field=None):
    return {"code": code, "label": label, "reason": reason,
            "severity": severity, "field": field}


def _minor(student) -> bool | None:
    birth = getattr(student, "birth_date", None) if student else None
    if birth is None:
        return None
    if hasattr(birth, "date"):
        birth = birth.date()
    try:
        today = datetime.utcnow().date()
        years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return years < 18
    except Exception:
        return None


def evaluate_position_publishability(position, company, batch, student=None,
                                     operation="PUBLISH", db=None) -> dict:
    rules = get_batch_compliance_rules(db, batch)
    cfg = rules.get("workRights") or {}
    required_fields = [
        "workContent", "dailyHours", "weeklyHours", "nightShift",
        "overtimeAllowed", "restDaysPerWeek", "remunerationType",
        "accommodationProvided", "mealProvided", "hazardousFlag",
    ]
    blockers, warnings, unknowns = [], [], []
    facts = {
        "companyId": str(getattr(company, "id", "") or ""),
        "batchId": str(getattr(batch, "id", "") or ""),
        "positionBatchId": str(_fact(position, "batch_id") or ""),
        "workContent": _fact(position, "work_content"),
        "workAddress": _fact(position, "work_address") or _fact(position, "work_location"),
        "dailyHours": _fact(position, "daily_hours"),
        "weeklyHours": _fact(position, "weekly_hours"),
        "nightShift": _fact(position, "night_shift"),
        "overtimeAllowed": _fact(position, "overtime_allowed"),
        "restDaysPerWeek": _fact(position, "rest_days_per_week"),
        "remunerationType": _fact(position, "remuneration_type"),
        "remunerationAmount": _fact(position, "remuneration_amount"),
        "remunerationCycle": _fact(position, "remuneration_cycle"),
        "accommodationProvided": _fact(position, "accommodation_provided"),
        "mealProvided": _fact(position, "meal_provided"),
        "hazardousFlag": _fact(position, "hazardous_flag"),
        "specialEquipment": _fact(position, "special_equipment"),
        "prohibitedReason": _fact(position, "prohibited_reason"),
        "headcount": _fact(position, "headcount"),
        "allocatedCount": _fact(position, "allocated_count"),
    }
    if position is None:
        blockers.append(_issue("POSITION_MISSING", "岗位", "岗位不存在"))
    if company is None:
        blockers.append(_issue("COMPANY_MISSING", "企业", "企业不存在"))
    else:
        if bool(getattr(company, "blacklist", False)) or getattr(company, "coop_status", None) == "BLACKLIST":
            blockers.append(_issue("COMPANY_BLACKLIST", "企业黑名单", "黑名单企业不能发布或分配岗位"))
        elif getattr(company, "coop_status", None) != "ACTIVE":
            blockers.append(_issue("COMPANY_INACTIVE", "企业合作状态", "企业不是合作中状态"))
        if db is not None and cfg.get("requireEnterpriseAccess", True):
            from app.modules.internship.services.internship_enterprise_inspection_service import (
                is_enterprise_access_valid,
            )
            ok, reason = is_enterprise_access_valid(db, company.id, rules)
            if not ok:
                blockers.append(_issue("ENTERPRISE_ACCESS_INVALID", "企业准入",
                                       reason or "企业准入无效或已过期"))
    if batch is None or not _fact(position, "batch_id"):
        unknowns.append(_issue("BATCH_UNKNOWN", "实习批次", "岗位未关联有效批次", field="batchId"))
    elif int(_fact(position, "batch_id")) != int(getattr(batch, "id", 0)):
        blockers.append(_issue("BATCH_MISMATCH", "实习批次", "岗位不属于当前批次"))

    field_map = {
        "workContent": "work_content", "dailyHours": "daily_hours",
        "weeklyHours": "weekly_hours", "nightShift": "night_shift",
        "overtimeAllowed": "overtime_allowed", "restDaysPerWeek": "rest_days_per_week",
        "remunerationType": "remuneration_type",
        "accommodationProvided": "accommodation_provided",
        "mealProvided": "meal_provided", "hazardousFlag": "hazardous_flag",
    }
    for api_name, attr in field_map.items():
        value = _fact(position, attr)
        if value is None or (isinstance(value, str) and not value.strip()):
            unknowns.append(_issue("REQUIRED_UNKNOWN", api_name,
                                   f"{api_name} 未录入，不能解释为安全", field=api_name))
    maximum = float(cfg.get("maxDailyHours", 8))
    if facts["dailyHours"] is not None and float(facts["dailyHours"]) > maximum:
        blockers.append(_issue("DAILY_HOURS_EXCEEDED", "每日工时",
                               f"每日工时超过规则上限 {maximum:g} 小时", field="dailyHours"))
    maximum_week = float(cfg.get("maxWeeklyHours", 40))
    if facts["weeklyHours"] is not None and float(facts["weeklyHours"]) > maximum_week:
        blockers.append(_issue("WEEKLY_HOURS_EXCEEDED", "每周工时",
                               f"每周工时超过规则上限 {maximum_week:g} 小时", field="weeklyHours"))
    if facts["nightShift"] is True:
        if not cfg.get("nightShiftAllowed", False):
            blockers.append(_issue("NIGHT_SHIFT_FORBIDDEN", "夜班", "当前批次规则不允许夜班"))
        if _minor(student) is True:
            blockers.append(_issue("MINOR_NIGHT_SHIFT", "未成年人夜班", "未成年人不得安排夜班"))
        warnings.append(_issue("NIGHT_SHIFT_FILING", "夜班备案", "夜班须完成特殊备案", severity="WARN"))
    if facts["overtimeAllowed"] is True and not cfg.get("overtimeAllowed", False):
        blockers.append(_issue("OVERTIME_FORBIDDEN", "加班", "当前规则不允许安排加班"))
    if facts["hazardousFlag"] is True:
        blockers.append(_issue("HAZARDOUS_POSITION", "危险岗位", "危险岗位不得直接发布或分配"))
    if facts["specialEquipment"] and not cfg.get("specialEquipmentAllowed", False):
        warnings.append(_issue("SPECIAL_EQUIPMENT", "特殊设备", "涉及特殊设备，须核验资质与备案",
                               severity="WARN"))
    if facts["prohibitedReason"]:
        blockers.append(_issue("PROHIBITED_REASON", "禁止安排说明", str(facts["prohibitedReason"])))
    if facts["remunerationType"] not in (None, "UNPAID"):
        if facts["remunerationAmount"] is None:
            unknowns.append(_issue("REMUNERATION_AMOUNT_UNKNOWN", "报酬金额",
                                   "有报酬岗位必须填写金额", field="remunerationAmount"))
        if not facts["remunerationCycle"]:
            unknowns.append(_issue("REMUNERATION_CYCLE_UNKNOWN", "发放周期",
                                   "有报酬岗位必须填写发放周期", field="remunerationCycle"))
    if facts["headcount"] is not None and facts["allocatedCount"] is not None:
        if int(facts["allocatedCount"]) >= int(facts["headcount"]):
            blockers.append(_issue("POSITION_FULL", "岗位容量", "岗位已满员"))
    return {
        "passed": not blockers and not unknowns,
        "blockers": blockers,
        "warnings": warnings,
        "unknowns": unknowns,
        "ruleVersion": rule_version_label(batch),
        "evaluatedAt": datetime.utcnow().isoformat() + "Z",
        "requiredFields": required_fields,
        "facts": facts,
        "operation": operation,
    }


def evaluate_position_compliance(position, student, rules, company=None, batch=None, db=None) -> dict:
    """旧调用兼容层；返回同一评估器结论，不再维护第二套规则。"""
    result = evaluate_position_publishability(
        position, company, batch, student, operation="ASSIGN", db=db)
    return {
        **result,
        "blockers": [x["reason"] for x in result["blockers"] + result["unknowns"]],
        "warnings": [x["reason"] for x in result["warnings"]],
    }
