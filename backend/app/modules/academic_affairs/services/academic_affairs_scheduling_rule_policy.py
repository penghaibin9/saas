"""V2-03 排课规则中心最终业务策略。

本层只开放自动排课引擎当前真实消费的 9 个规则键，把内部 key 映射为中文业务元数据，
并统一执行范围、状态和值域校验。数据库仍复用 t_aa_schedule_rule，不新增平行规则表。
"""
from __future__ import annotations

import json
from copy import deepcopy

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_autoschedule_service as _auto
from . import academic_affairs_scheduling_service as _scheduling


RULE_CATALOG = {
    "AUTO_DEFAULT_WEEKS": {
        "label": "默认上课周次",
        "group": "教学周范围",
        "control": "WEEK_RANGE",
        "description": "教学任务未填写起止周时，自动排课采用的默认教学周范围。",
        "defaultValue": {"startWeek": 1, "endWeek": 18},
        "required": True,
    },
    "AUTO_WEEKDAYS": {
        "label": "允许排课星期",
        "group": "可排时间",
        "control": "WEEKDAY_MULTI",
        "description": "自动排课可使用的星期；默认周一至周五，可按学校实际开放周末。",
        "defaultValue": [1, 2, 3, 4, 5],
        "required": True,
    },
    "AUTO_SLOTS": {
        "label": "允许排课节次",
        "group": "可排时间",
        "control": "SLOT_MULTI",
        "description": "自动排课可使用的作息节次，以学校已启用节次为准。",
        "defaultValue": [1, 2, 3, 4, 5, 6, 7, 8],
        "required": True,
    },
    "AUTO_FORBIDDEN": {
        "label": "统一禁排时段",
        "group": "可排时间",
        "control": "FORBIDDEN_GRID",
        "description": "全校统一禁止自动排课的星期和节次；不选具体节次表示整天禁排。",
        "defaultValue": [],
        "required": False,
    },
    "AUTO_CLASS_MAX_PER_DAY": {
        "label": "同班每日最多节次",
        "group": "每日负荷",
        "control": "INTEGER",
        "description": "同一行政班每天允许自动排入的最大节次数。",
        "defaultValue": 8,
        "required": True,
        "min": 1,
        "max": 24,
        "unit": "节",
    },
    "AUTO_TEACHER_MAX_PER_DAY": {
        "label": "同教师每日最多节次",
        "group": "每日负荷",
        "control": "INTEGER",
        "description": "同一任课教师每天允许自动排入的最大节次数。",
        "defaultValue": 6,
        "required": True,
        "min": 1,
        "max": 24,
        "unit": "节",
    },
    "AUTO_ROOM_TYPE_MATCH": {
        "label": "严格匹配教室类型",
        "group": "教室约束",
        "control": "BOOLEAN",
        "description": "开启后，实训课、机房课等只能进入教学任务指定类型的教室。",
        "defaultValue": True,
        "required": True,
    },
    "AUTO_CAPACITY_CHECK": {
        "label": "校验教室容量",
        "group": "教室约束",
        "control": "BOOLEAN",
        "description": "开启后，教室有效座位不足上课人数时禁止排入。",
        "defaultValue": True,
        "required": True,
    },
    "AUTO_RESPECT_TEACHER_AVAIL": {
        "label": "遵守教师不可排时间",
        "group": "教师约束",
        "control": "BOOLEAN",
        "description": "开启后，学院已采纳的教师不可排时段会从候选时间中排除。",
        "defaultValue": True,
        "required": True,
    },
}

WEEKDAY_OPTIONS = [
    {"value": 1, "label": "周一"}, {"value": 2, "label": "周二"},
    {"value": 3, "label": "周三"}, {"value": 4, "label": "周四"},
    {"value": 5, "label": "周五"}, {"value": 6, "label": "周六"},
    {"value": 7, "label": "周日"},
]


def _bad(message: str):
    return AppException("VALIDATION_ERROR", message)


def _conflict(message: str):
    return AppException("DATA_CONFLICT", message, http_status=409)


def _strict_int(value, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _bad(f"{label}必须是整数")
    if value < minimum or value > maximum:
        raise _bad(f"{label}必须在 {minimum}—{maximum} 之间")
    return int(value)


def _normalized_int_list(value, label: str, minimum: int, maximum: int, allowed=None) -> list[int]:
    if not isinstance(value, list) or not value:
        raise _bad(f"{label}至少选择一项")
    result = sorted({_strict_int(item, label, minimum, maximum) for item in value})
    if allowed:
        invalid = [item for item in result if item not in allowed]
        if invalid:
            raise _bad(f"{label}包含未启用项：{','.join(str(item) for item in invalid)}")
    return result


def normalize_rule_value(rule_key: str, value, *, teaching_weeks=None, enabled_slots=None):
    """纯值域校验，供服务与测试共用；返回稳定、去重、可直接序列化的值。"""
    key = str(rule_key or "").strip().upper()
    meta = RULE_CATALOG.get(key)
    if not meta:
        raise _bad("该排课参数不受当前自动排课引擎支持")

    control = meta["control"]
    if control == "WEEK_RANGE":
        if not isinstance(value, dict):
            raise _bad("默认上课周次必须包含起始周和结束周")
        start = _strict_int(value.get("startWeek"), "起始周", 1, 30)
        end = _strict_int(value.get("endWeek"), "结束周", 1, 30)
        if start > end:
            raise _bad("起始周不能晚于结束周")
        if teaching_weeks and end > int(teaching_weeks):
            raise _bad(f"结束周不能超过该学期教学周数 {int(teaching_weeks)}")
        return {"startWeek": start, "endWeek": end}

    if control == "WEEKDAY_MULTI":
        return _normalized_int_list(value, "允许排课星期", 1, 7)

    if control == "SLOT_MULTI":
        allowed = {int(item) for item in (enabled_slots or [])} or None
        return _normalized_int_list(value, "允许排课节次", 1, 30, allowed)

    if control == "FORBIDDEN_GRID":
        if not isinstance(value, list):
            raise _bad("统一禁排时段必须是时段列表")
        allowed = {int(item) for item in (enabled_slots or [])} or None
        seen = set()
        result = []
        for item in value:
            if not isinstance(item, dict):
                raise _bad("统一禁排时段存在非法记录")
            weekday = _strict_int(item.get("weekday"), "禁排星期", 1, 7)
            slot_raw = item.get("slotNo")
            slot_no = None if slot_raw in (None, "") else _strict_int(slot_raw, "禁排节次", 1, 30)
            if allowed and slot_no is not None and slot_no not in allowed:
                raise _bad(f"禁排节次 {slot_no} 未在学校启用节次中")
            signature = (weekday, slot_no)
            if signature in seen:
                continue
            seen.add(signature)
            row = {"weekday": weekday}
            if slot_no is not None:
                row["slotNo"] = slot_no
            result.append(row)
        return sorted(result, key=lambda row: (row["weekday"], row.get("slotNo") or 0))

    if control == "INTEGER":
        return _strict_int(value, meta["label"], int(meta["min"]), int(meta["max"]))

    if control == "BOOLEAN":
        if not isinstance(value, bool):
            raise _bad(f"{meta['label']}只能选择开启或关闭")
        return bool(value)

    raise _bad("排课参数控件类型未实现")


def summarize_rule_value(rule_key: str, value) -> str:
    key = str(rule_key or "").strip().upper()
    meta = RULE_CATALOG.get(key) or {}
    control = meta.get("control")
    if control == "WEEK_RANGE" and isinstance(value, dict):
        return f"第{value.get('startWeek', '—')}—{value.get('endWeek', '—')}周"
    if control == "WEEKDAY_MULTI" and isinstance(value, list):
        labels = {row["value"]: row["label"] for row in WEEKDAY_OPTIONS}
        return "、".join(labels.get(item, str(item)) for item in value) or "未设置"
    if control == "SLOT_MULTI" and isinstance(value, list):
        return "、".join(f"第{item}节" for item in value) or "未设置"
    if control == "FORBIDDEN_GRID" and isinstance(value, list):
        labels = {row["value"]: row["label"] for row in WEEKDAY_OPTIONS}
        text = []
        for row in value:
            day = labels.get(row.get("weekday"), str(row.get("weekday") or ""))
            text.append(f"{day}整天" if row.get("slotNo") is None else f"{day}第{row.get('slotNo')}节")
        return "、".join(text) if text else "不设统一禁排"
    if control == "INTEGER":
        return f"{value}{meta.get('unit', '')}"
    if control == "BOOLEAN":
        return "开启" if value is True else "关闭"
    return "配置异常"


def _catalog_item(rule_key: str) -> dict:
    item = deepcopy(RULE_CATALOG[rule_key])
    item["ruleKey"] = rule_key
    if item["control"] == "WEEKDAY_MULTI":
        item["options"] = deepcopy(WEEKDAY_OPTIONS)
    return item


def rule_catalog(user) -> dict:
    """返回中文业务元数据；保留 defaults 字段兼容既有调用方。"""
    items = [_catalog_item(key) for key in RULE_CATALOG]
    return {
        "items": items,
        "defaults": {
            "weekdays": [1, 2, 3, 4, 5],
            "slots": [1, 2, 3, 4, 5, 6, 7, 8],
            "classMaxPerDay": 8,
            "teacherMaxPerDay": 6,
            "roomTypeMatch": True,
            "capacityCheck": True,
            "respectAvail": True,
            "startWeek": 1,
            "endWeek": 18,
        },
    }


def _safe_json(raw):
    if raw in (None, ""):
        return None, False, ""
    try:
        return json.loads(raw), False, ""
    except (TypeError, ValueError):
        return None, True, "历史配置内容损坏，请重新保存或删除该规则"


def _rule_dto(row):
    value, invalid, message = _safe_json(row.rule_value_json)
    key = str(row.rule_key or "").strip().upper()
    meta = RULE_CATALOG.get(key)
    if not meta:
        invalid = True
        message = message or "该历史规则已不被当前自动排课引擎支持"
    elif not invalid:
        try:
            value = normalize_rule_value(key, value)
        except AppException as exc:
            invalid = True
            message = str(getattr(exc, "message", None) or exc)
    return {
        "ruleId": str(row.id),
        "termId": str(row.term_id) if row.term_id else None,
        "batchId": str(row.batch_id) if row.batch_id else None,
        "scopeType": "BATCH" if row.batch_id else ("TERM" if row.term_id else "LEGACY_GLOBAL"),
        "ruleKey": key,
        "ruleLabel": meta["label"] if meta else "历史未知规则",
        "ruleGroup": meta["group"] if meta else "待清理",
        "control": meta["control"] if meta else "UNKNOWN",
        "ruleValue": value,
        "valueSummary": summarize_rule_value(key, value) if meta and not invalid else "配置异常",
        "remark": row.remark or "",
        "status": row.status,
        "invalidValue": invalid,
        "validationMessage": message,
    }


def _resolve_write_scope(db, term_id, batch_id):
    from app.models import AaScheduleBatch, AaTerm
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    term = None
    batch = None
    if batch_id:
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise _conflict("该课表批次已经发布或归档，不能再修改排课参数")
        if term_id and int(term_id) != int(batch.term_id):
            raise _bad("课表批次与所选学期不一致")
        term_id = int(batch.term_id)

    if not term_id:
        raise _bad("请选择规则所属学期")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise not_found("学期不存在")
    guard_term_writable(db, int(term.id))
    return term, batch


def _enabled_slots(db) -> list[int]:
    from app.models import AaTimeSlot

    rows = db.query(AaTimeSlot.slot_no).filter(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.enabled.is_(True),
        AaTimeSlot.status == "ENABLED",
        AaTimeSlot.is_deleted.is_(False),
    ).all()
    return sorted({int(value) for (value,) in rows})


def save_rule(user, body):
    """按真实规则目录保存/更新；非法 key、范围、状态和值一律 fail-closed。"""
    from app.models import AaScheduleRule

    with session() as db:
        _scheduling._require_school(_scheduling._ctx(user, db))
        key = str(getattr(body, "ruleKey", None) or "").strip().upper()
        if key not in RULE_CATALOG:
            raise _bad("该排课参数不受当前自动排课引擎支持")
        term_id = int(body.termId) if getattr(body, "termId", None) else None
        batch_id = int(body.batchId) if getattr(body, "batchId", None) else None
        term, _batch = _resolve_write_scope(db, term_id, batch_id)
        value = normalize_rule_value(
            key,
            getattr(body, "ruleValue", None),
            teaching_weeks=term.teaching_weeks,
            enabled_slots=_enabled_slots(db),
        )
        row = db.query(AaScheduleRule).filter(
            AaScheduleRule.tenant_id == _tid(),
            AaScheduleRule.rule_key == key,
            AaScheduleRule.term_id == int(term.id),
            AaScheduleRule.batch_id == batch_id,
            AaScheduleRule.is_deleted.is_(False),
        ).first()
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        remark = str(getattr(body, "remark", None) or "").strip() or None
        if row:
            row.rule_value_json = encoded
            row.remark = remark
            row.status = "ENABLED"
        else:
            row = AaScheduleRule(
                tenant_id=_tid(),
                term_id=int(term.id),
                batch_id=batch_id,
                rule_key=key,
                rule_value_json=encoded,
                remark=remark,
                status="ENABLED",
            )
            db.add(row)
        db.flush()
        label = RULE_CATALOG[key]["label"]
        _scheduling._audit(
            db,
            "AA_SCHEDULE_RULE",
            row.id,
            "SCHEDULE_RULE_SAVE",
            f"{label};scope={'BATCH' if batch_id else 'TERM'};termId={term.id};batchId={batch_id or ''};value={summarize_rule_value(key, value)}",
        )
        db.commit()
        return _rule_dto(row)


def delete_rule(user, rule_id):
    from app.models import AaScheduleRule

    with session() as db:
        _scheduling._require_school(_scheduling._ctx(user, db))
        row = db.query(AaScheduleRule).filter(
            AaScheduleRule.id == int(rule_id),
            AaScheduleRule.tenant_id == _tid(),
            AaScheduleRule.is_deleted.is_(False),
        ).first()
        if not row:
            raise not_found("规则不存在")
        _resolve_write_scope(db, row.term_id, row.batch_id)
        row.is_deleted = True
        label = (RULE_CATALOG.get(row.rule_key) or {}).get("label") or row.rule_key
        _scheduling._audit(db, "AA_SCHEDULE_RULE", row.id, "SCHEDULE_RULE_DELETE", str(label))
        db.commit()
        return {"ruleId": str(row.id), "deleted": True}


# 路由仍导入原服务名；在包初始化阶段替换最终函数，避免复制千行 router。
_scheduling._rule_dto = _rule_dto
_scheduling.save_rule = save_rule
_scheduling.delete_rule = delete_rule
_auto.rule_catalog = rule_catalog
