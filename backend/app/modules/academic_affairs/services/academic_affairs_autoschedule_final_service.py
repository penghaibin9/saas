"""自动排课最终公开入口。

修正课表批次与教学任务批次错位，所有任务、规则、教师不可排时间均按课表批次的正式学期解析。
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_schedule_policy as policy

_base = importlib.import_module(
    ".academic_affairs_autoschedule_service",
    package=__package__,
)

REASON_LABEL = {
    **_base.REASON_LABEL,
    "INVALID_TASK": "教学任务周学时或周次配置无效",
}


def __getattr__(name):
    return getattr(_base, name)


def _pending_tasks_for_batch(db, schedule_batch, teaching_weeks: int) -> tuple[list, list]:
    from app.models import AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch

    task_batch_query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _base._tid(),
        AaTeachingTaskBatch.term_id == int(schedule_batch.term_id),
        AaTeachingTaskBatch.status == "APPROVED",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    if getattr(schedule_batch, "college_id", None):
        task_batch_query = task_batch_query.filter(
            AaTeachingTaskBatch.college_id == int(schedule_batch.college_id)
        )
    task_batch_ids = [int(row.id) for row in task_batch_query.all()]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _base._tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    done: dict[int, int] = {}
    for item in db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _base._tid(),
        AaScheduleItem.batch_id == int(schedule_batch.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all():
        if item.task_id:
            done[int(item.task_id)] = done.get(int(item.task_id), 0) + 1

    pending = []
    invalid = []
    for task in tasks:
        weekly_hours = int(task.weekly_hours or 0)
        start_week = int(task.start_week or 1)
        end_week = int(task.end_week or teaching_weeks)
        if (
            weekly_hours <= 0
            or start_week < 1
            or end_week < start_week
            or end_week > teaching_weeks
        ):
            invalid.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "className": task.teaching_class_name,
                "weeklyHours": task.weekly_hours,
                "startWeek": task.start_week,
                "endWeek": task.end_week,
                "reason": "INVALID_TASK",
                "reasonLabel": REASON_LABEL["INVALID_TASK"],
                "detail": f"请把周学时设为正整数，起止周控制在 1 至 {teaching_weeks} 周内",
            })
            continue
        already = int(done.get(int(task.id), 0))
        if already < weekly_hours:
            pending.append((task, weekly_hours - already, already, start_week, end_week))
    return pending, invalid


def auto_schedule(user, batch_id, dry_run=False) -> dict:
    from app.models import (
        AaScheduleBatch,
        AaScheduleItem,
        AaTeacherAvailability,
    )

    with _base.session() as db:
        _base._require_school(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("课表批次不存在")
        policy.resolve_scope(
            db,
            term_id=batch.term_id,
            batch_id=batch.id,
            writable=True,
        )
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException(
                "DATA_CONFLICT",
                "已发布课表不可自动排课，请走调停课或作废重发流程",
                http_status=409,
            )

        params = policy.effective_params(db, int(batch.term_id), int(batch.id))
        forbidden = _base._forbidden_set(params)
        grid = _base._build_grid(db, batch.id)
        rooms = _base._load_rooms(db, params)
        pending, invalid_tasks = _pending_tasks_for_batch(
            db,
            batch,
            int(params["teachingWeeks"]),
        )

        availability = set()
        if params["respectAvail"]:
            rows = db.query(AaTeacherAvailability).filter(
                AaTeacherAvailability.tenant_id == _base._tid(),
                AaTeacherAvailability.term_id == int(batch.term_id),
                AaTeacherAvailability.status == "ADOPTED",
                AaTeacherAvailability.is_deleted.is_(False),
            ).all()
            availability = {
                (row.teacher_key, int(row.weekday), int(row.slot_no))
                for row in rows
            }

        def tightness(item):
            task, _need, _have, _start_week, _end_week = item
            candidates = _base._room_candidates(
                rooms,
                task.required_room_type,
                task.expected_students,
                params,
            )
            return (len(candidates), -(task.expected_students or 0), int(task.id))

        pending.sort(key=tightness)
        capacity_warnings = []
        if params["capacityCheck"]:
            capacity_warnings = [{
                "taskId": str(task.id),
                "courseName": task.course_name,
                "className": task.teaching_class_name,
                "reason": "NO_HEADCOUNT",
                "detail": "未填写预计人数，容量校验对该任务失效；请先补齐预计人数再正式排课",
            } for task, _need, _have, _sw, _ew in pending if not task.expected_students]

        placed = []
        misses = list(invalid_tasks)
        new_items = []
        for task, need, have, start_week, end_week in pending:
            candidate_rooms = _base._room_candidates(
                rooms,
                task.required_room_type,
                task.expected_students,
                params,
            )
            positions, reason = _base._place_task(
                task,
                need,
                start_week,
                end_week,
                "ALL",
                params,
                forbidden,
                grid,
                candidate_rooms,
                rooms,
                availability,
            )
            for weekday, slot_no, room in positions:
                new_items.append({
                    "task": task,
                    "weekday": weekday,
                    "slotNo": slot_no,
                    "room": room,
                    "startWeek": start_week,
                    "endWeek": end_week,
                })
            if len(positions) < need:
                final_reason = "PARTIAL" if positions else reason
                misses.append({
                    "taskId": str(task.id),
                    "courseName": task.course_name,
                    "className": task.teaching_class_name,
                    "teacherName": task.teacher_name,
                    "needSessions": need,
                    "placedSessions": len(positions) + have,
                    "reason": final_reason,
                    "reasonLabel": REASON_LABEL.get(final_reason, final_reason),
                    "detail": _base._miss_detail(task, final_reason, params),
                })
            if positions:
                placed.append({
                    "taskId": str(task.id),
                    "courseName": task.course_name,
                    "sessions": len(positions),
                })

        reset_pre_publish = False
        if not dry_run and new_items:
            for item in new_items:
                task = item["task"]
                room = item["room"]
                db.add(AaScheduleItem(
                    tenant_id=_base._tid(),
                    batch_id=batch.id,
                    task_id=task.id,
                    course_id=task.course_id,
                    course_name=task.course_name,
                    class_id=task.class_id,
                    class_name=task.teaching_class_name,
                    teacher_key=task.teacher_key,
                    teacher_name=task.teacher_name,
                    weekday=item["weekday"],
                    slot_no=item["slotNo"],
                    start_week=item["startWeek"],
                    end_week=item["endWeek"],
                    week_parity="ALL",
                    classroom_id=(room.id if room else None),
                    classroom_text=(_base._room_label(room) if room else None),
                    status="EFFECTIVE",
                    source="AUTO",
                ))
            if batch.status == "PRE_PUBLISHED":
                batch.status = "DRAFT"
                reset_pre_publish = True
            _base._audit(
                db,
                batch.id,
                "AUTO_SCHEDULE",
                (
                    f"termId={batch.term_id};排入{len(new_items)}节/{len(placed)}个任务；"
                    f"漏排{len(misses)}；ruleVersion={params['ruleVersion']}"
                ),
            )
            db.commit()

        return {
            "batchId": str(batch.id),
            "termId": str(batch.term_id),
            "dryRun": bool(dry_run),
            "placedSessions": len(new_items),
            "placedTasks": len(placed),
            "missedTasks": len(misses),
            "invalidTaskCount": len(invalid_tasks),
            "roomPoolSize": len(rooms),
            "params": params,
            "placed": placed,
            "misses": misses,
            "capacityWarnings": capacity_warnings,
            "prePublishReset": reset_pre_publish,
        }


def miss_report(user, batch_id) -> dict:
    result = auto_schedule(user, batch_id, dry_run=True)
    grouped = {}
    for item in result["misses"]:
        grouped.setdefault(item["reason"], []).append(item)
    return {
        "batchId": result["batchId"],
        "termId": result["termId"],
        "wouldPlaceSessions": result["placedSessions"],
        "missedTasks": result["missedTasks"],
        "invalidTaskCount": result["invalidTaskCount"],
        "roomPoolSize": result["roomPoolSize"],
        "params": result["params"],
        "summary": [{
            "reason": reason,
            "reasonLabel": REASON_LABEL.get(reason, reason),
            "count": len(items),
        } for reason, items in sorted(grouped.items(), key=lambda pair: -len(pair[1]))],
        "misses": result["misses"],
        "capacityWarnings": result["capacityWarnings"],
    }


def clear_auto_items(user, batch_id) -> dict:
    from app.models import AaScheduleBatch, AaScheduleItem

    with _base.session() as db:
        _base._require_school(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("课表批次不存在")
        policy.resolve_scope(
            db,
            term_id=batch.term_id,
            batch_id=batch.id,
            writable=True,
        )
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException("DATA_CONFLICT", "已发布课表不可清除自动排课结果", http_status=409)
        rows = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _base._tid(),
            AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.source == "AUTO",
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().all()
        for row in rows:
            row.is_deleted = True
        reset_pre_publish = batch.status == "PRE_PUBLISHED" and bool(rows)
        if reset_pre_publish:
            batch.status = "DRAFT"
        _base._audit(
            db,
            batch.id,
            "AUTO_SCHEDULE_CLEAR",
            f"清除自动排课 {len(rows)} 节；人工/导入项保留",
        )
        db.commit()
        return {
            "batchId": str(batch.id),
            "cleared": len(rows),
            "prePublishReset": reset_pre_publish,
        }
