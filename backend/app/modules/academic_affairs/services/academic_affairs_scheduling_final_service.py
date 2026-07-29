"""排课规则、教师不可排时间和冲突报告最终公开入口。"""
from __future__ import annotations

import importlib
import json
from datetime import datetime

from app.core.affairs_security import _derive_keys
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_schedule_policy as policy

_base = importlib.import_module(
    ".academic_affairs_scheduling_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def _stable_teacher_key(user) -> str:
    ctx = get_current_user_ctx() or {}
    keys = {str(item) for item in _derive_keys(user) if str(item or "").strip()}
    uid = str(ctx.get("userId") or "").strip()
    candidates = [
        str(ctx.get("loginName") or "").strip(),
        str(ctx.get("employeeNo") or "").strip(),
        uid[2:] if uid.startswith("u_") else uid,
        uid,
    ]
    for candidate in candidates:
        if candidate and (not keys or candidate in keys):
            return candidate
    if keys:
        return sorted(keys)[0]
    raise AppException("DATA_CONFLICT", "当前账号缺少稳定教师标识，不能提交不可排时间", http_status=409)


def save_rule(user, body):
    from app.models import AaScheduleRule

    key = str(getattr(body, "ruleKey", None) or "").strip().upper()
    with _base.session() as db:
        _base._require_school(_base._ctx(user, db))
        term, batch, _weeks = policy.resolve_scope(
            db,
            term_id=getattr(body, "termId", None),
            batch_id=getattr(body, "batchId", None),
            writable=True,
        )
        value = policy.validate_rule_value(
            db,
            key,
            getattr(body, "ruleValue", None),
            term_id=term.id,
        )
        row = db.query(AaScheduleRule).filter(
            AaScheduleRule.tenant_id == _base._tid(),
            AaScheduleRule.rule_key == key,
            AaScheduleRule.term_id == term.id,
            AaScheduleRule.batch_id == (batch.id if batch else None),
        ).with_for_update().first()
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if row:
            row.rule_value_json = payload
            row.remark = getattr(body, "remark", None)
            row.status = "ENABLED"
            row.is_deleted = False
        else:
            row = AaScheduleRule(
                tenant_id=_base._tid(),
                term_id=term.id,
                batch_id=(batch.id if batch else None),
                rule_key=key,
                rule_value_json=payload,
                remark=getattr(body, "remark", None),
                status="ENABLED",
            )
            db.add(row)
        db.flush()
        _base._audit(
            db,
            "AA_SCHEDULE_RULE",
            row.id,
            "SCHEDULE_RULE_SAVE",
            f"{key};scope={'BATCH' if batch else 'TERM'};version=AA_SCHEDULE_RULE_V2",
        )
        db.commit()
        return _base._rule_dto(row)


def delete_rule(user, rule_id):
    from app.models import AaScheduleRule

    with _base.session() as db:
        _base._require_school(_base._ctx(user, db))
        row = db.query(AaScheduleRule).filter(
            AaScheduleRule.id == int(rule_id),
            AaScheduleRule.tenant_id == _base._tid(),
            AaScheduleRule.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("规则不存在")
        policy.resolve_scope(
            db,
            term_id=row.term_id,
            batch_id=row.batch_id,
            writable=True,
        )
        row.is_deleted = True
        _base._audit(db, "AA_SCHEDULE_RULE", row.id, "SCHEDULE_RULE_DELETE", row.rule_key)
        db.commit()
        return {"ruleId": str(row.id), "deleted": True}


def submit_availability(user, body):
    from app.models import AaTeacherAvailability

    term_id = getattr(body, "termId", None)
    if not term_id:
        raise AppException("VALIDATION_ERROR", "教师不可排时间必须绑定正式学期")
    weekday = int(body.weekday)
    slot_no = int(body.slotNo)
    if weekday < 1 or weekday > 7:
        raise AppException("VALIDATION_ERROR", "星期只能为 1 至 7")

    with _base.session() as db:
        term, _batch, _weeks = policy.resolve_scope(
            db,
            term_id=term_id,
            writable=True,
        )
        if slot_no not in policy.enabled_slots(db):
            raise AppException("VALIDATION_ERROR", "所选节次未启用")
        teacher_key = _stable_teacher_key(user)
        ctx = get_current_user_ctx() or {}
        row = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _base._tid(),
            AaTeacherAvailability.teacher_key == teacher_key,
            AaTeacherAvailability.term_id == term.id,
            AaTeacherAvailability.weekday == weekday,
            AaTeacherAvailability.slot_no == slot_no,
        ).with_for_update().first()
        if row:
            row.reason = getattr(body, "reason", None)
            row.review_reason = None
            row.status = "PENDING"
            row.is_deleted = False
        else:
            row = AaTeacherAvailability(
                tenant_id=_base._tid(),
                teacher_key=teacher_key,
                teacher_name=ctx.get("realName"),
                term_id=term.id,
                weekday=weekday,
                slot_no=slot_no,
                reason=getattr(body, "reason", None),
                status="PENDING",
            )
            db.add(row)
        db.flush()
        _base._audit(
            db,
            "AA_TEACHER_AVAIL",
            row.id,
            "TEACHER_AVAIL_SUBMIT",
            f"termId={term.id};周{weekday}第{slot_no}节",
        )
        db.commit()
        return _base._avail_dto(row)


def review_availability(user, avail_id, action, reason=""):
    from app.models import AaTeacherAvailability

    action = str(action or "").strip().upper()
    reason_text = str(reason or "").strip()
    with _base.session() as db:
        _base._require_school(_base._ctx(user, db))
        row = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.id == int(avail_id),
            AaTeacherAvailability.tenant_id == _base._tid(),
            AaTeacherAvailability.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("教师不可排时间记录不存在")
        policy.resolve_scope(db, term_id=row.term_id, writable=True)
        if row.status != "PENDING":
            raise _base._invalid("仅待处理记录可采纳或驳回")
        if action == "ADOPT":
            row.status = "ADOPTED"
            row.review_reason = None
        elif action == "REJECT":
            if len(reason_text) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            row.status = "REJECTED"
            row.review_reason = reason_text
        else:
            raise AppException("VALIDATION_ERROR", "动作仅支持 ADOPT/REJECT")
        _base._audit(
            db,
            "AA_TEACHER_AVAIL",
            row.id,
            "TEACHER_AVAIL_REVIEW",
            f"{action};termId={row.term_id}",
        )
        db.commit()
        return _base._avail_dto(row)


def conflict_report_in_session(db, batch) -> dict:
    from app.models import AaScheduleItem, AaTeacherAvailability

    items = db.query(AaScheduleItem).filter(
        AaScheduleItem.batch_id == int(batch.id),
        AaScheduleItem.tenant_id == _base._tid(),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()
    hard = []
    for left_index, left in enumerate(items):
        for right in items[left_index + 1:]:
            if left.weekday != right.weekday or left.slot_no != right.slot_no:
                continue
            if not _base._weeks_overlap(
                left.start_week,
                left.end_week,
                left.week_parity,
                right.start_week,
                right.end_week,
                right.week_parity,
            ):
                continue
            dimension = None
            if left.teacher_key and left.teacher_key == right.teacher_key:
                dimension = "TEACHER"
            elif left.class_id and right.class_id and int(left.class_id) == int(right.class_id):
                dimension = "CLASS"
            elif (
                left.classroom_id and right.classroom_id
                and int(left.classroom_id) == int(right.classroom_id)
            ) or (
                not left.classroom_id and not right.classroom_id
                and left.classroom_text and left.classroom_text == right.classroom_text
            ):
                dimension = "CLASSROOM"
            if dimension:
                hard.append({
                    "level": "HARD",
                    "dimension": dimension,
                    "weekday": left.weekday,
                    "slotNo": left.slot_no,
                    "itemA": {
                        "id": str(left.id),
                        "courseName": left.course_name,
                        "className": left.class_name,
                        "teacherName": left.teacher_name,
                        "classroom": left.classroom_text,
                    },
                    "itemB": {
                        "id": str(right.id),
                        "courseName": right.course_name,
                        "className": right.class_name,
                        "teacherName": right.teacher_name,
                        "classroom": right.classroom_text,
                    },
                })

    adopted = db.query(AaTeacherAvailability).filter(
        AaTeacherAvailability.tenant_id == _base._tid(),
        AaTeacherAvailability.term_id == int(batch.term_id),
        AaTeacherAvailability.status == "ADOPTED",
        AaTeacherAvailability.is_deleted.is_(False),
    ).all()
    availability = {(row.teacher_key, row.weekday, row.slot_no) for row in adopted}
    soft = []
    for item in items:
        if item.teacher_key and (item.teacher_key, item.weekday, item.slot_no) in availability:
            soft.append({
                "level": "SOFT",
                "dimension": "TEACHER_UNAVAILABLE",
                "weekday": item.weekday,
                "slotNo": item.slot_no,
                "item": {
                    "id": str(item.id),
                    "courseName": item.course_name,
                    "teacherName": item.teacher_name,
                },
            })
    return {
        "batchId": str(batch.id),
        "termId": str(batch.term_id),
        "hardCount": len(hard),
        "softCount": len(soft),
        "canPrePublish": len(hard) == 0,
        "hardConflicts": hard,
        "softConflicts": soft,
        "ruleVersion": "AA_SCHEDULE_RULE_V2",
    }


def conflict_report(user, batch_id):
    from app.models import AaScheduleBatch

    with _base.session() as db:
        _base._ctx(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        return conflict_report_in_session(db, batch)


def summary(user, batch_id):
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch

    with _base.session() as db:
        _base._ctx(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        task_batch_ids = [row.id for row in db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == _base._tid(),
            AaTeachingTaskBatch.term_id == int(batch.term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).all()]
        tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _base._tid(),
            AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
            AaTeachingTask.status == "READY",
            AaTeachingTask.no_auto_schedule.is_(False),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        items = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _base._tid(),
            AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        ).all()
        task_map = {int(row.id): row for row in tasks}
        counts = {}
        orphan_items = []
        for item in items:
            if not item.task_id or int(item.task_id) not in task_map:
                orphan_items.append(item)
                continue
            counts[int(item.task_id)] = counts.get(int(item.task_id), 0) + 1
        missing = []
        over = []
        for task in tasks:
            expected = int(task.weekly_hours or 0)
            actual = int(counts.get(int(task.id), 0))
            if expected <= 0 or actual < expected:
                missing.append({
                    "taskId": str(task.id),
                    "courseName": task.course_name,
                    "expectedSessions": expected,
                    "scheduledSessions": actual,
                })
            elif actual > expected:
                over.append({
                    "taskId": str(task.id),
                    "courseName": task.course_name,
                    "expectedSessions": expected,
                    "scheduledSessions": actual,
                })
        conflicts = conflict_report_in_session(db, batch)
        expected_sessions = sum(max(0, int(task.weekly_hours or 0)) for task in tasks)
        scheduled_sessions = sum(counts.values())
        complete = not missing and not over and not orphan_items and conflicts["hardCount"] == 0
        return {
            "batchId": str(batch.id),
            "termId": str(batch.term_id),
            "batchStatus": batch.status,
            "totalTasks": len(tasks),
            "scheduledTasks": len(counts),
            "completionRate": round(len(counts) / len(tasks) * 100, 1) if tasks else 0.0,
            "scheduledHours": scheduled_sessions,
            "expectedHours": expected_sessions,
            "hardConflicts": conflicts["hardCount"],
            "softConflicts": conflicts["softCount"],
            "missingTaskCount": len(missing),
            "overScheduledTaskCount": len(over),
            "orphanItemCount": len(orphan_items),
            "missingTasks": missing,
            "overScheduledTasks": over,
            "orphanItemIds": [str(item.id) for item in orphan_items],
            "complete": complete,
            "canPrePublish": complete,
            "ruleVersion": "AA_SCHEDULE_RULE_V2",
        }
