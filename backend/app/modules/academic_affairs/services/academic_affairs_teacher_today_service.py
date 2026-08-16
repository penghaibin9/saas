"""C-W2 Teacher Today read projection.

This module does not own schedule truth. It consumes the C-C1/B-C1 formal occurrence
projection already bound to current ScopeHead active batches and turns it into a teacher-facing
read model. It never creates ScopeHead, ScheduleItem, TeachingTask, Todo, or Attendance facts.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException, no_permission
from app.services.db_service import _tid, session

from . import academic_affairs_attendance_occurrence_consumer as occurrence
from .academic_affairs_attendance_service import ATTENDANCE_TASK_STATUSES

_NO_CLASS_CALENDAR_MESSAGES = {
    "该日期为校历调休停课日，不能创建普通课堂考勤": "SWAP_SOURCE",
    "该日期为节假日，不能创建普通课堂考勤": "HOLIDAY",
}


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", "日期格式必须为 YYYY-MM-DD") from exc


def _current_term(db):
    from app.models import AaTerm

    rows = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(),
        AaTerm.is_current.is_(True),
        AaTerm.is_deleted.is_(False),
    )).all()
    if len(rows) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "当前租户存在多个当前学期，Teacher Today 无法确定教学时间轴",
            http_status=409,
        )
    return rows[0] if rows else None


def _teacher_keys(user) -> set[str]:
    if str((user or {}).get("userType") or "").upper() == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    keys = {str(value).strip() for value in _derive_keys(user or {}) if str(value).strip()}
    if not keys:
        raise no_permission("当前教师账号缺少稳定工号，请联系管理员")
    return keys


def _teacher_schedule_in_session(db, user) -> tuple[dict, object | None]:
    from app.models import AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch, SchoolClass

    keys = _teacher_keys(user)
    term = _current_term(db)
    if not term:
        return {
            "termId": "",
            "termCode": "",
            "termStartDate": None,
            "termEndDate": None,
            "teachingWeeks": None,
            "hasData": False,
            "items": [],
            "issues": [],
            "note": "学校尚未设置当前学期",
        }, None

    task_batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term.id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    batch_by_id = {int(row.id): row for row in task_batches}
    batch_ids = sorted(batch_by_id)

    tasks = []
    if batch_ids:
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids),
            AaTeachingTask.teacher_key.in_(sorted(keys)),
            AaTeachingTask.status.in_(sorted(ATTENDANCE_TASK_STATUSES)),
            AaTeachingTask.is_deleted.is_(False),
        )).all()

    bindings = [
        (task, batch_by_id[int(task.batch_id)])
        for task in tasks
        if int(task.batch_id) in batch_by_id
    ]
    formal_by_task = occurrence.formal_schedule_patterns_for_tasks(db, bindings, term)

    class_ids = sorted({int(task.class_id) for task in tasks if task.class_id})
    class_by_id = {}
    if class_ids:
        class_rows = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(class_ids),
            SchoolClass.is_deleted.is_(False),
        )).all()
        class_by_id = {int(row.id): row for row in class_rows}

    schedule_item_ids = sorted({
        int(pattern["scheduleItemId"])
        for formal in formal_by_task.values()
        for pattern in formal.get("patterns") or []
        if pattern.get("scheduleItemId")
    })
    schedule_item_by_id = {}
    if schedule_item_ids:
        schedule_rows = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(),
            AaScheduleItem.id.in_(schedule_item_ids),
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        )).all()
        schedule_item_by_id = {int(row.id): row for row in schedule_rows}

    items = []
    issues = []
    for task, _task_batch in bindings:
        formal = formal_by_task.get(int(task.id), {
            "status": "CONFLICT",
            "issue": "无法读取当前正式课表",
            "patterns": [],
        })
        if formal.get("status") != "READY":
            issues.append({
                "teachingTaskId": str(task.id),
                "courseName": task.course_name or "",
                "status": formal.get("status") or "CONFLICT",
                "message": formal.get("issue") or "当前教学任务没有可消费的正式课次",
            })
            continue
        school_class = class_by_id.get(int(task.class_id or 0))
        for pattern in formal.get("patterns") or []:
            schedule_item_id = int(pattern["scheduleItemId"])
            schedule_row = schedule_item_by_id.get(schedule_item_id)
            if not schedule_row:
                issues.append({
                    "teachingTaskId": str(task.id),
                    "scheduleItemId": str(schedule_item_id),
                    "status": "CONFLICT",
                    "message": "正式课次投影对应的 ScheduleItem 已失效，请刷新",
                })
                continue
            items.append({
                "sourceType": "FORMAL_TEACHING",
                "scheduleItemId": str(schedule_item_id),
                "activeBatchId": pattern["activeBatchId"],
                "scopeType": pattern["scopeType"],
                "scopeId": pattern["scopeId"],
                "scopeHeadVersion": pattern["scopeHeadVersion"],
                "teachingTaskId": str(task.id),
                "taskStatus": task.status,
                "courseName": task.course_name or schedule_row.course_name or "",
                "classId": str(task.class_id or ""),
                "className": (
                    getattr(school_class, "class_name", None)
                    or getattr(task, "teaching_class_name", None)
                    or schedule_row.class_name
                    or ""
                ),
                "teacherKey": task.teacher_key or "",
                "teacherName": task.teacher_name or schedule_row.teacher_name or "",
                "weekday": int(pattern["weekday"]),
                "slotNo": int(pattern["slotNo"]),
                "startWeek": int(pattern["startWeek"]),
                "endWeek": int(pattern["endWeek"]),
                "weekParity": pattern["weekParity"],
                "classroom": schedule_row.classroom_text or "",
                "changeId": pattern.get("changeId"),
                "changeType": pattern.get("changeType"),
                "changeAppliedAt": pattern.get("changeAppliedAt"),
            })

    items.sort(key=lambda row: (
        int(row["weekday"]),
        int(row["slotNo"]),
        int(row["startWeek"]),
        int(row["scheduleItemId"]),
    ))
    term_start = _as_date(term.start_date)
    term_end = _as_date(term.end_date)
    return {
        "termId": str(term.id),
        "termCode": f"{term.year_code}-{term.term_no}",
        "termStartDate": term_start.isoformat() if term_start else None,
        "termEndDate": term_end.isoformat() if term_end else None,
        "teachingWeeks": int(term.teaching_weeks or 0) or None,
        "hasData": bool(items),
        "items": items,
        "issues": issues,
        "note": "只消费当前 ScopeHead 正式课表；历史/最近 PUBLISHED 非 Authority 批次不会进入教师视图",
    }, term


def teacher_schedule_projection(user) -> dict:
    """All current formal occurrences for the authenticated teacher, bounded and read-only."""
    with session() as db:
        result, _term = _teacher_schedule_in_session(db, user)
        return result


def _today_value(db, on_date=None) -> date:
    if on_date is not None:
        value = _as_date(on_date)
        if value is None:
            raise AppException("VALIDATION_ERROR", "日期不能为空")
        return value
    from app.modules.academic_affairs.services.student_exam_read_service import _tenant_timezone

    zone, _zone_name = _tenant_timezone(db)
    return datetime.now(zone).date()


def _pattern_active(row: dict, *, week_no: int, weekday: int) -> bool:
    if int(row.get("weekday") or 0) != int(weekday):
        return False
    start = int(row.get("startWeek") or 0)
    end = int(row.get("endWeek") or 0)
    if start and week_no < start:
        return False
    if end and week_no > end:
        return False
    parity = str(row.get("weekParity") or "ALL").upper()
    if parity == "ODD" and week_no % 2 == 0:
        return False
    if parity == "EVEN" and week_no % 2 == 1:
        return False
    if parity not in {"ALL", "ODD", "EVEN"}:
        raise AppException("DATA_CONFLICT", "正式课表存在未知单双周配置", http_status=409)
    return True


def _legacy_mobile_meta(db, term) -> dict:
    """Preserve existing mobile timetable metadata without using its batch-selection logic."""
    if not term:
        return {"timezone": None, "timeBands": []}
    from . import mobile_academic_affairs_facade as mobile_facade

    _ignored_week, timezone_name = mobile_facade._current_teaching_week(db, term)
    return {
        "timezone": timezone_name,
        "timeBands": mobile_facade._schedule_time_bands(db),
    }


def teacher_today_projection(user, *, on_date=None) -> dict:
    """Today's formal occurrences with an exact attendance deep-link.

    Calendar semantics are delegated to the C-C1 occurrence resolver: HOLIDAY/SWAP source
    dates produce no class; SWAP target dates use the original teaching date for week/weekday
    matching while the attendance deep-link keeps the actual target date.
    """
    with session() as db:
        schedule, term = _teacher_schedule_in_session(db, user)
        target = _today_value(db, on_date)
        mobile_meta = _legacy_mobile_meta(db, term)
        base = {
            **schedule,
            **mobile_meta,
            "todayDate": target.isoformat(),
            "logicalDate": target.isoformat(),
            "calendarSource": "NORMAL",
            "calendarEventId": None,
            "currentWeek": None,
            "todayItems": [],
        }
        if not term:
            return base
        term_start = _as_date(term.start_date)
        term_end = _as_date(term.end_date)
        if not term_start or not term_end:
            raise AppException(
                "DATA_CONFLICT",
                "当前学期缺少起止日期，Teacher Today 无法确定正式课次",
                http_status=409,
            )
        if target < term_start or target > term_end:
            base["calendarSource"] = "OUT_OF_TERM"
            return base

        wall_week_no, _wall_weekday = occurrence._week_and_weekday(term, target)
        base["currentWeek"] = wall_week_no
        try:
            logical_date, calendar_source, calendar_event_id = occurrence._calendar_logical_date(
                db,
                term,
                target,
                lock=False,
            )
        except AppException as exc:
            source = _NO_CLASS_CALENDAR_MESSAGES.get(str(getattr(exc, "message", "") or ""))
            if not source:
                raise
            base["calendarSource"] = source
            return base

        week_no, weekday = occurrence._week_and_weekday(term, logical_date)
        today_items = []
        for row in schedule["items"]:
            if not _pattern_active(row, week_no=week_no, weekday=weekday):
                continue
            attendance_route = (
                "/pages/teacher/academic-affairs/attendance"
                f"?teachingTaskId={row['teachingTaskId']}"
                f"&sessionDate={target.isoformat()}"
                f"&slotNo={row['slotNo']}"
                f"&scheduleItemId={row['scheduleItemId']}"
            )
            today_items.append({
                **row,
                "sessionDate": target.isoformat(),
                "logicalDate": logical_date.isoformat(),
                "weekNo": week_no,
                "calendarSource": calendar_source,
                "calendarEventId": str(calendar_event_id) if calendar_event_id else None,
                "attendanceRoute": attendance_route,
            })

        today_items.sort(key=lambda row: (int(row["slotNo"]), int(row["scheduleItemId"])))
        base.update({
            "logicalDate": logical_date.isoformat(),
            "calendarSource": calendar_source,
            "calendarEventId": str(calendar_event_id) if calendar_event_id else None,
            "currentWeek": week_no,
            "todayItems": today_items,
        })
        return base
