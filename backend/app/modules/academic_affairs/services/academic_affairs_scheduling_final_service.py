"""排课规则、教师不可排时间和冲突报告最终公开入口。"""
from __future__ import annotations

import importlib
import json
from datetime import datetime

from app.core.affairs_security import _derive_keys
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_schedule_conflict_index as conflict_index
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
    for left, right in conflict_index.iter_same_slot_pairs(items):
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
    from app.models import (
        AaScheduleBatch,
        AaScheduleItem,
        AaTeacherAvailability,
        AaTeachingTask,
        AaTeachingTaskBatch,
    )

    with _base.session() as db:
        _base._ctx(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        task_batch_query = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.tenant_id == _base._tid(),
            AaTeachingTaskBatch.term_id == int(batch.term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        if batch.college_id:
            task_batch_query = task_batch_query.filter(
                AaTeachingTaskBatch.college_id == int(batch.college_id),
            )
        task_batches = task_batch_query.all()
        task_batch_ids = [row.id for row in task_batches]
        all_tasks = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _base._tid(),
            AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
            AaTeachingTask.status != "MERGED",
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        tasks = [
            row for row in all_tasks
            if row.status == "READY" and not bool(row.no_auto_schedule)
        ]
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
                    "courseCode": task.course_code,
                    "courseName": task.course_name,
                    "teacherName": task.teacher_name,
                    "teacherKey": task.teacher_key,
                    "classId": str(task.class_id) if task.class_id else None,
                    "className": task.teaching_class_name,
                    "weeklyHours": expected,
                    "totalHours": int(task.total_hours or 0),
                    "startWeek": task.start_week,
                    "endWeek": task.end_week,
                    "requiredRoomType": task.required_room_type,
                    "expectedSessions": expected,
                    "scheduledSessions": actual,
                    "remainingSessions": max(0, expected - actual),
                    "issueType": "UNSCHEDULED" if actual == 0 else "PARTIAL",
                    "issueLabel": "未排" if actual == 0 else "部分漏排",
                    "canSchedule": True,
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
        task_status_counts = {}
        for task in all_tasks:
            task_status_counts[task.status] = task_status_counts.get(task.status, 0) + 1
        confirmed_task_count = sum(
            1 for task in all_tasks if task.status in {"TEACHER_CONFIRMED", "READY"}
        )
        not_ready = [
            task for task in all_tasks
            if task.status != "READY" and not bool(task.no_auto_schedule)
        ]
        invalid_queue = [{
            "taskId": str(task.id),
            "courseCode": task.course_code,
            "courseName": task.course_name,
            "teacherName": task.teacher_name,
            "teacherKey": task.teacher_key,
            "classId": str(task.class_id) if task.class_id else None,
            "className": task.teaching_class_name,
            "weeklyHours": int(task.weekly_hours or 0),
            "totalHours": int(task.total_hours or 0),
            "startWeek": task.start_week,
            "endWeek": task.end_week,
            "requiredRoomType": task.required_room_type,
            "expectedSessions": int(task.weekly_hours or 0),
            "scheduledSessions": 0,
            "remainingSessions": max(0, int(task.weekly_hours or 0)),
            "issueType": "NOT_READY",
            "issueLabel": "教学任务未就绪",
            "taskStatus": task.status,
            "canSchedule": False,
        } for task in not_ready]
        full_task_queue = sorted(
            [*missing, *invalid_queue],
            key=lambda row: ({"UNSCHEDULED": 0, "PARTIAL": 1, "NOT_READY": 2}.get(row["issueType"], 9),
                             str(row.get("courseName") or "")),
        )
        task_queue = full_task_queue[:100]
        pending_availability_count = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _base._tid(),
            AaTeacherAvailability.term_id == int(batch.term_id),
            AaTeacherAvailability.status == "PENDING",
            AaTeacherAvailability.is_deleted.is_(False),
        ).count()
        teacher_objection_count = sum(1 for item in items if item.objection_status == "PENDING")
        complete = not missing and not over and not orphan_items and conflicts["hardCount"] == 0

        blockers = []
        if not all_tasks:
            blockers.append("本学期还没有可供排课的教学任务")
        if not_ready:
            blockers.append(f"{len(not_ready)} 个教学任务尚未达到 READY")
        if pending_availability_count:
            blockers.append(f"{pending_availability_count} 条教师不可排时间待处理")
        if missing:
            blockers.append(f"{len(missing)} 个教学任务仍有未排节次")
        if over:
            blockers.append(f"{len(over)} 个教学任务排课超量")
        if orphan_items:
            blockers.append(f"{len(orphan_items)} 个课位无法回溯教学任务")
        if conflicts["hardCount"]:
            blockers.append(f"{conflicts['hardCount']} 个硬冲突必须清零")
        if batch.status == "PRE_PUBLISHED" and teacher_objection_count:
            blockers.append(f"{teacher_objection_count} 条教师异议待处理")

        if batch.status in {"PUBLISHED", "SUPERSEDED", "ARCHIVED"}:
            current_stage_key = "PUBLISH"
            next_action = {
                "code": "CHANGE_LEDGER" if batch.status == "PUBLISHED" else "READ_ONLY",
                "label": "进入调停课台账" if batch.status == "PUBLISHED" else "查看历史课表",
                "description": "正式课表日常变更走调停课审批" if batch.status == "PUBLISHED" else "该批次只读留痕",
            }
        elif batch.status == "PRE_PUBLISHED":
            current_stage_key = "PRE_PUBLISH"
            next_action = {
                "code": "HANDLE_OBJECTIONS" if teacher_objection_count else "PUBLISH",
                "label": "处理教师异议" if teacher_objection_count else "正式发布",
                "description": "异议清零后再正式发布" if teacher_objection_count else "发布后同步教师、学生四端课表",
            }
        elif not all_tasks or not_ready:
            current_stage_key = "PREPARE"
            next_action = {"code": "TEACHING_TASKS", "label": "完善教学任务", "description": "先完成教师、班级、周学时和周次确认"}
        elif pending_availability_count and not scheduled_sessions:
            current_stage_key = "PREFERENCE"
            next_action = {"code": "AVAILABILITY", "label": "处理教师偏好", "description": "采纳或驳回待处理的不可排时间"}
        elif not scheduled_sessions:
            current_stage_key = "AUTO"
            next_action = {"code": "AUTO_DRY_RUN", "label": "执行试排预览", "description": "先预览，不写入正式课表"}
        elif missing:
            current_stage_key = "MANUAL"
            next_action = {"code": "TASK_QUEUE", "label": "处理未排与漏排", "description": "从任务队列逐项补齐剩余节次"}
        else:
            current_stage_key = "QUALITY"
            next_action = {
                "code": "CONFLICTS" if conflicts["hardCount"] else "PRE_PUBLISH",
                "label": "处理硬冲突" if conflicts["hardCount"] else "进入预发布检查",
                "description": "硬冲突必须清零" if conflicts["hardCount"] else "排课完整，可执行预发布闸门",
            }

        stage_order = [
            ("PREPARE", "数据准备"),
            ("PREFERENCE", "教师偏好"),
            ("AUTO", "自动初排"),
            ("MANUAL", "人工微调"),
            ("QUALITY", "冲突与漏排"),
            ("PRE_PUBLISH", "预发布"),
            ("PUBLISH", "正式发布"),
        ]
        current_index = next(i for i, row in enumerate(stage_order) if row[0] == current_stage_key)
        workflow_steps = [{
            "key": key,
            "label": label,
            "state": "completed" if index < current_index else ("current" if index == current_index else "pending"),
        } for index, (key, label) in enumerate(stage_order)]
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "termId": str(batch.term_id),
            "batchStatus": batch.status,
            "totalTasks": len(all_tasks),
            "readyTaskCount": len(tasks),
            "confirmedTaskCount": confirmed_task_count,
            "notReadyTaskCount": len(not_ready),
            "excludedTaskCount": sum(1 for task in all_tasks if bool(task.no_auto_schedule)),
            "scheduledTasks": len(counts),
            "completionRate": round(len(counts) / len(tasks) * 100, 1) if tasks else 0.0,
            "scheduledHours": scheduled_sessions,
            "expectedHours": expected_sessions,
            "hardConflicts": conflicts["hardCount"],
            "softConflicts": conflicts["softCount"],
            "missingTaskCount": len(missing),
            "unplacedTaskCount": sum(1 for row in missing if row["issueType"] == "UNSCHEDULED"),
            "partiallyScheduledTaskCount": sum(1 for row in missing if row["issueType"] == "PARTIAL"),
            "overScheduledTaskCount": len(over),
            "orphanItemCount": len(orphan_items),
            "pendingAvailabilityCount": pending_availability_count,
            "teacherObjectionCount": teacher_objection_count,
            "taskStatusCounts": task_status_counts,
            "missingTasks": missing,
            "taskQueue": task_queue,
            "taskQueueTotal": len(full_task_queue),
            "overScheduledTasks": over,
            "orphanItemIds": [str(item.id) for item in orphan_items],
            "complete": complete,
            "canPrePublish": complete,
            "workflow": {
                "currentStageKey": current_stage_key,
                "steps": workflow_steps,
                "blockers": blockers,
                "nextAction": next_action,
            },
            "ruleVersion": "AA_SCHEDULE_RULE_V2",
        }
