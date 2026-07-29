"""排课规则唯一语义与正式学期坐标校验。"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

RULE_SCHEMAS = {
    "AUTO_DEFAULT_WEEKS": "WEEK_RANGE",
    "AUTO_WEEKDAYS": "WEEKDAY_LIST",
    "AUTO_SLOTS": "SLOT_LIST",
    "AUTO_FORBIDDEN": "FORBIDDEN_LIST",
    "AUTO_CLASS_MAX_PER_DAY": "POSITIVE_INT",
    "AUTO_TEACHER_MAX_PER_DAY": "POSITIVE_INT",
    "AUTO_ROOM_TYPE_MATCH": "BOOL",
    "AUTO_CAPACITY_CHECK": "BOOL",
    "AUTO_RESPECT_TEACHER_AVAIL": "BOOL",
}


def _conflict(message: str, *, details=None):
    raise AppException("DATA_CONFLICT", message, details=details, http_status=409)


def term_bounds(db, term_id: int) -> tuple[object, int]:
    from app.models import AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise not_found("学期不存在")
    weeks = int(term.teaching_weeks or 0)
    if weeks < 1 or weeks > 30:
        _conflict(
            "正式学期尚未配置有效教学周数，不能排课",
            details={"termId": str(term.id), "teachingWeeks": term.teaching_weeks},
        )
    return term, weeks


def enabled_slots(db) -> list[int]:
    from app.models import AaTimeSlot

    rows = db.query(AaTimeSlot).filter(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.enabled.is_(True),
        AaTimeSlot.status == "ENABLED",
        AaTimeSlot.is_deleted.is_(False),
    ).order_by(AaTimeSlot.slot_no).all()
    slots = sorted({int(row.slot_no) for row in rows if int(row.slot_no or 0) > 0})
    if not slots:
        _conflict("学校尚未配置启用的作息节次，不能排课")
    return slots


def resolve_scope(db, *, term_id=None, batch_id=None, writable=False):
    from app.models import AaScheduleBatch

    batch = None
    resolved_term_id = int(term_id) if term_id not in (None, "") else None
    if batch_id not in (None, ""):
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        if resolved_term_id and resolved_term_id != int(batch.term_id):
            _conflict("排课规则的学期与课表批次不一致")
        resolved_term_id = int(batch.term_id)
    if not resolved_term_id:
        raise AppException("VALIDATION_ERROR", "排课规则必须绑定正式学期或课表批次")
    term, weeks = term_bounds(db, resolved_term_id)
    if writable:
        from . import academic_affairs_archive_service as archive_service
        archive_service.guard_term_writable(db, term.id)
    return term, batch, weeks


def _as_int(value, label: str) -> int:
    if isinstance(value, bool):
        raise AppException("VALIDATION_ERROR", f"{label}必须为整数")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label}必须为整数")


def validate_rule_value(db, key: str, value, *, term_id: int):
    key = str(key or "").strip().upper()
    schema = RULE_SCHEMAS.get(key)
    if not schema:
        raise AppException("VALIDATION_ERROR", f"不支持的排课规则：{key or '-'}")
    _term, weeks = term_bounds(db, int(term_id))
    slots = enabled_slots(db)

    if schema == "BOOL":
        if type(value) is not bool:
            raise AppException("VALIDATION_ERROR", f"{key} 必须为 true/false")
        return value
    if schema == "POSITIVE_INT":
        number = _as_int(value, key)
        if number < 1 or number > len(slots):
            raise AppException("VALIDATION_ERROR", f"{key} 必须在 1 至 {len(slots)} 之间")
        return number
    if schema == "WEEK_RANGE":
        if not isinstance(value, dict):
            raise AppException("VALIDATION_ERROR", "AUTO_DEFAULT_WEEKS 必须为对象")
        start = _as_int(value.get("startWeek"), "startWeek")
        end = _as_int(value.get("endWeek"), "endWeek")
        if start < 1 or end < start or end > weeks:
            raise AppException("VALIDATION_ERROR", f"默认周次必须在 1 至 {weeks} 周内且起始周不大于结束周")
        return {"startWeek": start, "endWeek": end}
    if schema == "WEEKDAY_LIST":
        if not isinstance(value, list) or not value:
            raise AppException("VALIDATION_ERROR", "AUTO_WEEKDAYS 必须为非空数组")
        result = sorted({_as_int(item, "weekday") for item in value})
        if any(item < 1 or item > 7 for item in result):
            raise AppException("VALIDATION_ERROR", "可排星期只能为 1 至 7")
        return result
    if schema == "SLOT_LIST":
        if not isinstance(value, list) or not value:
            raise AppException("VALIDATION_ERROR", "AUTO_SLOTS 必须为非空数组")
        result = sorted({_as_int(item, "slotNo") for item in value})
        invalid = [item for item in result if item not in slots]
        if invalid:
            raise AppException("VALIDATION_ERROR", f"包含未启用节次：{invalid}")
        return result
    if schema == "FORBIDDEN_LIST":
        if not isinstance(value, list):
            raise AppException("VALIDATION_ERROR", "AUTO_FORBIDDEN 必须为数组")
        result = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise AppException("VALIDATION_ERROR", f"第 {index} 条禁排规则必须为对象")
            weekday = _as_int(item.get("weekday"), "weekday")
            if weekday < 1 or weekday > 7:
                raise AppException("VALIDATION_ERROR", f"第 {index} 条禁排规则星期非法")
            normalized = {"weekday": weekday}
            if item.get("slotNo") not in (None, ""):
                slot = _as_int(item.get("slotNo"), "slotNo")
                if slot not in slots:
                    raise AppException("VALIDATION_ERROR", f"第 {index} 条禁排规则节次未启用")
                normalized["slotNo"] = slot
            result.append(normalized)
        return result
    raise AppException("VALIDATION_ERROR", f"无法识别排课规则类型：{schema}")


def effective_params(db, term_id: int, batch_id: int) -> dict:
    from app.models import AaScheduleRule

    _term, weeks = term_bounds(db, int(term_id))
    slots = enabled_slots(db)
    rows = db.query(AaScheduleRule).filter(
        AaScheduleRule.tenant_id == _tid(),
        AaScheduleRule.status == "ENABLED",
        AaScheduleRule.is_deleted.is_(False),
    ).all()
    term_values = {}
    batch_values = {}
    for row in rows:
        if row.rule_key not in RULE_SCHEMAS:
            continue
        target = None
        if row.batch_id and int(row.batch_id) == int(batch_id):
            target = batch_values
        elif row.term_id and int(row.term_id) == int(term_id) and not row.batch_id:
            target = term_values
        if target is None:
            continue
        try:
            raw = json.loads(row.rule_value_json) if row.rule_value_json is not None else None
        except (TypeError, ValueError, json.JSONDecodeError):
            _conflict("排课规则数据损坏，请重新保存", details={"ruleId": str(row.id), "ruleKey": row.rule_key})
        target[row.rule_key] = validate_rule_value(db, row.rule_key, raw, term_id=term_id)
    merged = {**term_values, **batch_values}
    default_weeks = {"startWeek": 1, "endWeek": weeks}
    return {
        "startWeek": int((merged.get("AUTO_DEFAULT_WEEKS") or default_weeks)["startWeek"]),
        "endWeek": int((merged.get("AUTO_DEFAULT_WEEKS") or default_weeks)["endWeek"]),
        "weekdays": list(merged.get("AUTO_WEEKDAYS") or [1, 2, 3, 4, 5]),
        "slots": list(merged.get("AUTO_SLOTS") or slots),
        "forbidden": list(merged.get("AUTO_FORBIDDEN") or []),
        "classMaxPerDay": int(merged.get("AUTO_CLASS_MAX_PER_DAY") or min(8, len(slots))),
        "teacherMaxPerDay": int(merged.get("AUTO_TEACHER_MAX_PER_DAY") or min(6, len(slots))),
        "roomTypeMatch": bool(merged.get("AUTO_ROOM_TYPE_MATCH", True)),
        "capacityCheck": bool(merged.get("AUTO_CAPACITY_CHECK", True)),
        "respectAvail": bool(merged.get("AUTO_RESPECT_TEACHER_AVAIL", True)),
        "teachingWeeks": weeks,
        "enabledSlots": slots,
        "ruleVersion": "AA_SCHEDULE_RULE_V2",
    }
