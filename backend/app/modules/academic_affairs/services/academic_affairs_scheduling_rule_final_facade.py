"""V2-03 排课规则与教师不可排时间最终安全层。

在既有规则目录、独立路由和自动排课引擎之上收口以下生产缺口：
- 以学期行锁串行化规则写入，规避 MySQL nullable 唯一键允许重复学期级规则；
- 自动排课只消费经过目录和值域校验的有效规则，重复、损坏、未知规则一律 fail-closed；
- AUTO_SLOTS 的安全默认值来自学校真实启用节次，不再静默使用固定 1—8 节；
- 教师不可排时间校验正式学期和真实节次，学院仅可处理本院授课教师记录。
"""
from __future__ import annotations

import json
from copy import deepcopy

from sqlalchemy import and_, or_, select

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_autoschedule_service as _auto
from . import academic_affairs_scheduling_rule_policy as _policy
from . import academic_affairs_scheduling_rule_transport as _transport
from . import academic_affairs_scheduling_service as _scheduling

RULE_CATALOG = _policy.RULE_CATALOG


def __getattr__(name):
    return getattr(_policy, name)


def _conflict(message: str, *, details=None) -> AppException:
    return AppException("DATA_CONFLICT", message, details=details, http_status=409)


def _enabled_slots(db) -> list[int]:
    from app.models import AaTimeSlot

    rows = db.query(AaTimeSlot.slot_no).filter(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.enabled.is_(True),
        AaTimeSlot.status == "ENABLED",
        AaTimeSlot.is_deleted.is_(False),
    ).all()
    return sorted({int(value) for (value,) in rows})


def _normalize_for_engine(key: str, value, *, teaching_weeks=None, enabled_slots=None):
    """在既有值域校验之上补齐真实节次与整天禁排的最终语义。"""
    slots = list(enabled_slots or [])
    if key == "AUTO_SLOTS" and not slots:
        raise _conflict("学校尚未配置已启用作息节次，自动排课参数不可保存或执行")
    if key == "AUTO_FORBIDDEN":
        rows = value if isinstance(value, list) else []
        has_specific_slot = any(isinstance(row, dict) and row.get("slotNo") is not None for row in rows)
        if has_specific_slot and not slots:
            raise _conflict("学校尚未配置已启用作息节次，不能保存具体节次禁排规则")

    normalized = _policy.normalize_rule_value(
        key,
        value,
        teaching_weeks=teaching_weeks,
        enabled_slots=slots if slots else None,
    )
    if key != "AUTO_FORBIDDEN":
        return normalized

    # 同一星期配置“整天禁排”时，具体节次记录不再保留，避免引擎和页面出现双重事实。
    whole_days = {
        int(row["weekday"])
        for row in normalized
        if isinstance(row, dict) and row.get("slotNo") is None
    }
    return [
        row for row in normalized
        if row.get("slotNo") is None or int(row["weekday"]) not in whole_days
    ]


def _default_values(*, teaching_weeks, enabled_slots) -> dict:
    values = {key: deepcopy(meta["defaultValue"]) for key, meta in RULE_CATALOG.items()}
    maximum_week = max(1, int(teaching_weeks or 18))
    values["AUTO_DEFAULT_WEEKS"] = {"startWeek": 1, "endWeek": min(18, maximum_week)}
    values["AUTO_SLOTS"] = list(enabled_slots)
    return values


def _decode_rule_value(row, *, teaching_weeks, enabled_slots):
    key = str(row.rule_key or "").strip().upper()
    if key not in RULE_CATALOG:
        raise _conflict(
            f"排课参数存在当前引擎不支持的规则 {key or 'EMPTY'}，请先清理历史配置",
            details={"ruleId": str(row.id), "ruleKey": key},
        )
    try:
        raw = json.loads(row.rule_value_json) if row.rule_value_json is not None else None
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _conflict(
            f"排课规则“{RULE_CATALOG[key]['label']}”配置损坏，请重新保存后再自动排课",
            details={"ruleId": str(row.id), "ruleKey": key},
        ) from exc
    try:
        return key, _normalize_for_engine(
            key,
            raw,
            teaching_weeks=teaching_weeks,
            enabled_slots=enabled_slots,
        )
    except AppException as exc:
        raise _conflict(
            f"排课规则“{RULE_CATALOG[key]['label']}”配置无效：{exc.message}",
            details={"ruleId": str(row.id), "ruleKey": key},
        ) from exc


def _merge_rule_rows(rows, *, term_id, batch_id, teaching_weeks, enabled_slots) -> dict:
    """批次级覆盖学期级；任一层出现重复事实时拒绝执行，不做不确定的 last-write-wins。"""
    scoped: dict[str, dict[str, object]] = {"TERM": {}, "BATCH": {}}
    source_ids: dict[str, dict[str, str]] = {"TERM": {}, "BATCH": {}}
    for row in rows:
        is_batch = row.batch_id is not None
        scope = "BATCH" if is_batch else "TERM"
        if is_batch:
            if int(row.batch_id) != int(batch_id) or int(row.term_id or 0) != int(term_id):
                raise _conflict("批次级排课规则与课表批次学期不一致，请先治理数据")
        elif int(row.term_id or 0) != int(term_id):
            continue

        key, value = _decode_rule_value(
            row,
            teaching_weeks=teaching_weeks,
            enabled_slots=enabled_slots,
        )
        if key in scoped[scope]:
            raise _conflict(
                f"{scope == 'BATCH' and '批次级' or '学期级'}排课规则“{RULE_CATALOG[key]['label']}”存在重复记录，禁止自动排课",
                details={
                    "ruleKey": key,
                    "ruleIds": [source_ids[scope][key], str(row.id)],
                    "scope": scope,
                },
            )
        scoped[scope][key] = value
        source_ids[scope][key] = str(row.id)

    merged = _default_values(teaching_weeks=teaching_weeks, enabled_slots=enabled_slots)
    merged.update(scoped["TERM"])
    merged.update(scoped["BATCH"])
    return {
        "startWeek": int(merged["AUTO_DEFAULT_WEEKS"]["startWeek"]),
        "endWeek": int(merged["AUTO_DEFAULT_WEEKS"]["endWeek"]),
        "weekdays": list(merged["AUTO_WEEKDAYS"]),
        "slots": list(merged["AUTO_SLOTS"]),
        "forbidden": list(merged["AUTO_FORBIDDEN"]),
        "classMaxPerDay": int(merged["AUTO_CLASS_MAX_PER_DAY"]),
        "teacherMaxPerDay": int(merged["AUTO_TEACHER_MAX_PER_DAY"]),
        "roomTypeMatch": bool(merged["AUTO_ROOM_TYPE_MATCH"]),
        "capacityCheck": bool(merged["AUTO_CAPACITY_CHECK"]),
        "respectAvail": bool(merged["AUTO_RESPECT_TEACHER_AVAIL"]),
    }


def load_effective_params(db, term_id, batch_id) -> dict:
    """自动排课唯一参数读取入口：真实节次、严格目录、严格值域、重复事实拒绝。"""
    from app.models import AaScheduleBatch, AaScheduleRule, AaTerm

    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise not_found("课表批次所属学期不存在")
    batch = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.id == int(batch_id),
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.is_deleted.is_(False),
    ).first()
    if not batch or int(batch.term_id) != int(term.id):
        raise _conflict("课表批次与正式学期关系异常，禁止自动排课")

    slots = _enabled_slots(db)
    if not slots:
        raise _conflict("学校尚未配置已启用作息节次，禁止自动排课")

    rows = db.query(AaScheduleRule).filter(
        AaScheduleRule.tenant_id == _tid(),
        AaScheduleRule.status == "ENABLED",
        AaScheduleRule.is_deleted.is_(False),
        or_(
            and_(AaScheduleRule.term_id == term.id, AaScheduleRule.batch_id.is_(None)),
            and_(AaScheduleRule.term_id == term.id, AaScheduleRule.batch_id == batch.id),
        ),
    ).order_by(AaScheduleRule.id).all()
    return _merge_rule_rows(
        rows,
        term_id=term.id,
        batch_id=batch.id,
        teaching_weeks=term.teaching_weeks,
        enabled_slots=slots,
    )


def _lock_write_scope(db, term_id, batch_id):
    """固定先锁学期、后锁批次；同一学期规则写入串行化，避免 nullable 唯一键并发穿透。"""
    from app.models import AaScheduleBatch, AaTerm
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    batch = None
    if batch_id:
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        if term_id and int(term_id) != int(batch.term_id):
            raise _policy._bad("课表批次与所选学期不一致")
        term_id = int(batch.term_id)
    if not term_id:
        raise _policy._bad("请选择规则所属学期")

    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).with_for_update().first()
    if not term:
        raise not_found("学期不存在")
    guard_term_writable(db, term.id)

    if batch_id:
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch or int(batch.term_id) != int(term.id):
            raise _conflict("课表批次与所选学期不一致")
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise _conflict("该课表批次已经发布或归档，不能再修改排课参数")
    return term, batch


def save_rule(user, body):
    from app.models import AaScheduleRule

    body = _transport._RuleBodyProxy(body)
    with session() as db:
        _scheduling._require_school(_scheduling._ctx(user, db))
        key = str(getattr(body, "ruleKey", None) or "").strip().upper()
        if key not in RULE_CATALOG:
            raise _policy._bad("该排课参数不受当前自动排课引擎支持")
        term_id = int(body.termId) if getattr(body, "termId", None) else None
        batch_id = int(body.batchId) if getattr(body, "batchId", None) else None
        term, _batch = _lock_write_scope(db, term_id, batch_id)
        slots = _enabled_slots(db) if key in {"AUTO_SLOTS", "AUTO_FORBIDDEN"} else []
        value = _normalize_for_engine(
            key,
            getattr(body, "ruleValue", None),
            teaching_weeks=term.teaching_weeks,
            enabled_slots=slots,
        )

        rows = db.query(AaScheduleRule).filter(
            AaScheduleRule.tenant_id == _tid(),
            AaScheduleRule.rule_key == key,
            AaScheduleRule.term_id == int(term.id),
            AaScheduleRule.batch_id == batch_id,
            AaScheduleRule.is_deleted.is_(False),
        ).with_for_update().all()
        if len(rows) > 1:
            raise _conflict(
                f"排课规则“{RULE_CATALOG[key]['label']}”存在重复记录，请先治理后再保存",
                details={"ruleIds": [str(row.id) for row in rows], "ruleKey": key},
            )
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        remark = str(getattr(body, "remark", None) or "").strip() or None
        if rows:
            row = rows[0]
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
        _scheduling._audit(
            db,
            "AA_SCHEDULE_RULE",
            row.id,
            "SCHEDULE_RULE_SAVE_V2_FINAL",
            (
                f"{RULE_CATALOG[key]['label']};scope={'BATCH' if batch_id else 'TERM'};"
                f"termId={term.id};batchId={batch_id or ''};value={_policy.summarize_rule_value(key, value)}"
            ),
        )
        db.commit()
        return _policy._rule_dto(row)


def delete_rule(user, rule_id):
    from app.models import AaScheduleRule

    with session() as db:
        _scheduling._require_school(_scheduling._ctx(user, db))
        probe = db.query(AaScheduleRule).filter(
            AaScheduleRule.id == int(rule_id),
            AaScheduleRule.tenant_id == _tid(),
            AaScheduleRule.is_deleted.is_(False),
        ).first()
        if not probe:
            raise not_found("规则不存在")
        _lock_write_scope(db, probe.term_id, probe.batch_id)
        row = db.query(AaScheduleRule).filter(
            AaScheduleRule.id == int(rule_id),
            AaScheduleRule.tenant_id == _tid(),
            AaScheduleRule.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise AppException("APPROVAL_VERSION_CONFLICT", "规则已被其他操作删除", http_status=409)
        row.is_deleted = True
        label = (RULE_CATALOG.get(row.rule_key) or {}).get("label") or row.rule_key
        _scheduling._audit(db, "AA_SCHEDULE_RULE", row.id, "SCHEDULE_RULE_DELETE_V2_FINAL", str(label))
        db.commit()
        return {"ruleId": str(row.id), "deleted": True}


def _teacher_key(user) -> str:
    ctx = get_current_user_ctx() or {}
    uid = str(ctx.get("userId") or (user or {}).get("userId") or "")
    login = str(ctx.get("loginName") or (user or {}).get("loginName") or "").strip()
    key = login or (uid[2:] if uid.startswith("u_") else uid)
    if not key:
        keys = sorted(_derive_keys(user or {}))
        key = keys[0] if keys else ""
    if not key:
        raise AppException("NO_PERMISSION", "当前账号缺少稳定教师标识，不能提交不可排时间", http_status=403)
    return key


def _validate_availability_target(db, term_id, weekday, slot_no):
    from app.models import AaTerm, AaTimeSlot
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    if not term_id:
        raise _policy._bad("请选择不可排时间所属学期")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        raise not_found("学期不存在")
    guard_term_writable(db, term.id)
    day = int(weekday)
    slot = int(slot_no)
    if day < 1 or day > 7:
        raise _policy._bad("星期必须在1—7之间")
    enabled = db.query(AaTimeSlot.id).filter(
        AaTimeSlot.tenant_id == _tid(),
        AaTimeSlot.slot_no == slot,
        AaTimeSlot.enabled.is_(True),
        AaTimeSlot.status == "ENABLED",
        AaTimeSlot.is_deleted.is_(False),
    ).first()
    if not enabled:
        raise _conflict("所选节次未在学校作息中启用，不能登记不可排时间")
    return term, day, slot


def _college_teacher_keys(ctx, db, term_id=None) -> set[str]:
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    allowed_classes = ctx.allowed_class_ids(db)
    conditions = []
    if allowed_classes:
        conditions.append(AaTeachingTask.class_id.in_(list(allowed_classes)))
    if ctx.college_ids:
        conditions.append(AaTeachingTaskBatch.college_id.in_(list(ctx.college_ids)))
    if not conditions:
        return set()
    query = db.query(AaTeachingTask.teacher_key).join(
        AaTeachingTaskBatch,
        AaTeachingTask.batch_id == AaTeachingTaskBatch.id,
    ).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTask.teacher_key.isnot(None),
        AaTeachingTask.status.notin_(["MERGED", "CANCELLED"]),
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.is_deleted.is_(False),
        or_(*conditions),
    )
    if term_id:
        query = query.filter(AaTeachingTaskBatch.term_id == int(term_id))
    return {str(value) for (value,) in query.distinct().all() if value}


def _visible_availability_teacher_keys(user, ctx, db, term_id=None, *, mine=False):
    if mine:
        return _derive_keys(user or {})
    if ctx.scope_type == "TENANT_ALL":
        return None
    if ctx.scope_type == "COLLEGE":
        return _college_teacher_keys(ctx, db, term_id)
    return _derive_keys(user or {})


def submit_availability(user, body):
    from app.models import AaTeacherAvailability

    with session() as db:
        _scheduling._ctx(user, db)
        term, weekday, slot_no = _validate_availability_target(
            db,
            getattr(body, "termId", None),
            getattr(body, "weekday", None),
            getattr(body, "slotNo", None),
        )
        teacher_key = _teacher_key(user)
        row = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _tid(),
            AaTeacherAvailability.teacher_key == teacher_key,
            AaTeacherAvailability.term_id == term.id,
            AaTeacherAvailability.weekday == weekday,
            AaTeacherAvailability.slot_no == slot_no,
            AaTeacherAvailability.is_deleted.is_(False),
        ).with_for_update().first()
        reason = str(getattr(body, "reason", None) or "").strip() or None
        current = get_current_user_ctx() or {}
        if row:
            row.reason = reason
            row.review_reason = None
            row.status = "PENDING"
        else:
            row = AaTeacherAvailability(
                tenant_id=_tid(),
                teacher_key=teacher_key,
                teacher_name=current.get("realName") or (user or {}).get("realName"),
                term_id=term.id,
                weekday=weekday,
                slot_no=slot_no,
                reason=reason,
                status="PENDING",
            )
            db.add(row)
        db.flush()
        _scheduling._audit(
            db, "AA_TEACHER_AVAIL", row.id, "TEACHER_AVAIL_SUBMIT_V2_FINAL",
            f"termId={term.id};teacherKey={teacher_key};weekday={weekday};slotNo={slot_no}",
        )
        db.commit()
        return _scheduling._avail_dto(row)


def list_availability(user, term_id=None, teacher_key=None, status=None, mine=False):
    from app.models import AaTeacherAvailability

    with session() as db:
        ctx = _scheduling._ctx(user, db)
        query = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _tid(),
            AaTeacherAvailability.is_deleted.is_(False),
        )
        if term_id:
            query = query.filter(AaTeacherAvailability.term_id == int(term_id))
        if teacher_key:
            query = query.filter(AaTeacherAvailability.teacher_key == str(teacher_key))
        if status:
            query = query.filter(AaTeacherAvailability.status == str(status).upper())
        visible_keys = _visible_availability_teacher_keys(user, ctx, db, term_id, mine=bool(mine))
        if visible_keys is not None:
            query = query.filter(AaTeacherAvailability.teacher_key.in_(list(visible_keys) or [""]))
        return [_scheduling._avail_dto(row) for row in query.order_by(AaTeacherAvailability.id.desc()).all()]


def review_availability(user, avail_id, action, reason=""):
    from app.models import AaTeacherAvailability

    with session() as db:
        ctx = _scheduling._ctx(user, db)
        row = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.id == int(avail_id),
            AaTeacherAvailability.tenant_id == _tid(),
            AaTeacherAvailability.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("教师不可排时间记录不存在")
        visible_keys = _visible_availability_teacher_keys(user, ctx, db, row.term_id, mine=False)
        if visible_keys is not None and row.teacher_key not in visible_keys:
            raise no_data_scope("该教师不在您的学院授课范围内")
        if ctx.scope_type not in {"TENANT_ALL", "COLLEGE"}:
            raise no_data_scope("仅教务处或对应学院可处理教师不可排时间")
        _validate_availability_target(db, row.term_id, row.weekday, row.slot_no)
        if row.status != "PENDING":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该记录已处理，请刷新列表", http_status=409)

        action_code = str(action or "").strip().upper()
        if action_code == "ADOPT":
            row.status = "ADOPTED"
            row.review_reason = None
        elif action_code == "REJECT":
            reason_text = str(reason or "").strip()
            if len(reason_text) < 5:
                raise _policy._bad("驳回原因必填且不少于5字")
            row.status = "REJECTED"
            row.review_reason = reason_text
        else:
            raise _policy._bad("非法动作")
        _scheduling._audit(
            db, "AA_TEACHER_AVAIL", row.id, "TEACHER_AVAIL_REVIEW_V2_FINAL",
            f"action={action_code};scope={ctx.scope_type};termId={row.term_id};teacherKey={row.teacher_key}",
        )
        db.commit()
        return _scheduling._avail_dto(row)


# 最终注入：现有路由和自动排课调用方无需改 URL 或 import。
_auto._load_params = load_effective_params
_scheduling.save_rule = save_rule
_scheduling.delete_rule = delete_rule
_scheduling.submit_availability = submit_availability
_scheduling.list_availability = list_availability
_scheduling.review_availability = review_availability
