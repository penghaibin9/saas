"""排课规则唯一语义与正式学期坐标校验。"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

PUBLIC_SCHEDULE_MODES = {"SCHOOL_CENTRALIZED", "OFFERING_UNIT", "HYBRID"}
# 保留现有校级统筹、学院批次编排方式；学校可通过现有教务配置指定公共课责任。
DEFAULT_PUBLIC_SCHEDULE_MODE = "HYBRID"


def _field(row, name, default=None):
    return row.get(name, default) if isinstance(row, dict) else getattr(row, name, default)


def active_weeks(start, end, parity="ALL") -> tuple[int, ...]:
    """按学期绝对周号展开计划；不把校历停课或实际考勤混入计划学时。"""
    if parity not in {"ALL", "ODD", "EVEN"} or start < 1 or end < start:
        return ()
    return tuple(w for w in range(start, end + 1)
                 if parity == "ALL" or w % 2 == (1 if parity == "ODD" else 0))


def task_coverage(task, items, teaching_weeks: int) -> dict:
    """唯一计划课时计算；周学时是周上限，总学时可不整除教学周数。"""
    weekly = int(_field(task, "weekly_hours") or 0)
    raw_start, raw_end = _field(task, "start_week"), _field(task, "end_week")
    start = 1 if raw_start is None else int(raw_start)
    end = teaching_weeks if raw_end is None else int(raw_end)
    valid_window = 1 <= start <= end <= teaching_weeks <= 30
    raw_total = _field(task, "total_hours")
    derived = raw_total is None
    expected = weekly * (end - start + 1) if derived and valid_window else int(raw_total or 0)
    invalid_task = (weekly <= 0 or not valid_window or expected <= 0
                    or expected > weekly * (end - start + 1))
    counts = {week: 0 for week in range(start, end + 1)} if valid_window else {}
    invalid_items = []
    rows = list(items)
    for index, row in enumerate(rows):
        sw, ew = int(_field(row, "start_week") or 0), int(_field(row, "end_week") or 0)
        parity = _field(row, "week_parity")
        weeks = active_weeks(sw, ew, parity) if 1 <= sw <= ew <= teaching_weeks else ()
        if (not valid_window or sw < start or ew > end or not weeks
                or not 1 <= int(_field(row, "weekday") or 0) <= 7
                or int(_field(row, "slot_no") or 0) <= 0):
            invalid_items.append(str(_field(row, "id", f"candidate-{index}")))
            continue
        for week in weeks:
            counts[week] += 1
    scheduled = sum(counts.values())
    overloaded = [week for week, count in counts.items() if count > weekly]
    return {
        "expectedContactHours": max(0, expected),
        "scheduledContactHours": scheduled,
        "missingContactHours": max(0, expected - scheduled),
        "remainingContactHours": max(0, expected - scheduled),
        "excessContactHours": max(0, scheduled - max(0, expected)),
        # 单位为“任务—学期周”超量组合数，另保留超量任务数量。
        "weeklyOverloadCount": len(overloaded),
        "overloadedWeeks": overloaded,
        "weekContactHours": counts,
        "scheduledItemCount": len(rows),
        "invalidTask": invalid_task,
        "invalidItemIds": invalid_items,
        "totalHoursDerived": derived,
        "contactHourBasis": "旧任务按周学时和有效周窗推导" if derived else "任务计划总学时",
    }


def missing_week_segments(task, coverage) -> list[tuple[int, int, int]]:
    """把真实剩余学时拆成可由现行排课器安排的连续周窗和每周数量。"""
    if coverage["invalidTask"] or coverage["invalidItemIds"] or coverage["weeklyOverloadCount"]:
        return []
    counts = dict(coverage["weekContactHours"])
    remaining = coverage["missingContactHours"]
    weekly = int(_field(task, "weekly_hours"))
    segments = {}
    while remaining > 0:
        selected = []
        for week, count in counts.items():
            if count < weekly and remaining:
                selected.append(week)
                counts[week] += 1
                remaining -= 1
        if not selected:
            break
        start = end = selected[0]
        for week in selected[1:] + [None]:
            if week == end + 1:
                end = week
                continue
            segments[(start, end)] = segments.get((start, end), 0) + 1
            start = end = week
    return [(count, start, end) for (start, end), count in segments.items()]


def public_schedule_mode(db):
    from app.services.platform_service import _get_cfg
    row = _get_cfg(db, _tid(), "ACAD_RULE", "PUBLIC_SCHEDULE_MODE")
    mode = (row.config_json or {}).get("mode") if row and row.enabled else DEFAULT_PUBLIC_SCHEDULE_MODE
    if mode not in PUBLIC_SCHEDULE_MODES:
        _conflict("公共课排课责任配置无效，请由校教务核对")
    return mode


def task_scope_condition(db, batch, *, include_centralized_public=False):
    """所有排课入口按开课单位筛任务；批次学期/审批条件仍由原入口负责。"""
    from sqlalchemy import exists, func, or_, select, true
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch
    course_conditions = (AaCourse.id == AaTeachingTask.course_id, AaCourse.tenant_id == _tid(),
                         AaCourse.is_deleted.is_(False))
    mode = public_schedule_mode(db)
    public = exists(select(AaCourse.id).where(*course_conditions,
        or_(AaCourse.category == "PUBLIC_BASIC", AaCourse.nature == "PUBLIC_ELECTIVE")).correlate(AaTeachingTask))
    if not getattr(batch, "college_id", None):
        return public if mode == "SCHOOL_CENTRALIZED" else true()
    owner = select(AaCourse.owner_college_id).where(*course_conditions).correlate(AaTeachingTask).scalar_subquery()
    fallback = select(AaTeachingTaskBatch.college_id).where(
        AaTeachingTaskBatch.id == AaTeachingTask.batch_id, AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).correlate(AaTeachingTask).scalar_subquery()
    condition = func.coalesce(owner, fallback) == int(batch.college_id)
    if mode == "SCHOOL_CENTRALIZED" and not include_centralized_public:
        condition &= ~public
    return condition


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
