"""C-W1 formal attendance consumer for the frozen B-C1 Published Schedule Contract.

This module owns no schedule truth. It resolves one requested attendance date/slot against
existing ScopeHead active batches and EFFECTIVE schedule items; it never creates ScopeHead.
"""
from __future__ import annotations

from datetime import date, datetime

from app.core.exceptions import AppException
from app.services.db_service import _tid


def _conflict(message: str, *, details=None):
    raise AppException("DATA_CONFLICT", message, details=details, http_status=409)


def _date_value(value):
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", "考勤日期格式必须为 YYYY-MM-DD") from exc


def _calendar_logical_date(db, term, requested: date, *, lock: bool) -> tuple[date, str, int | None]:
    from app.models import AaCalendarEvent

    term_start = _date_value(getattr(term, "start_date", None))
    term_end = _date_value(getattr(term, "end_date", None))
    if not term_start or not term_end:
        _conflict("当前学期缺少起止日期，不能解析校历课次")
    if requested < term_start or requested > term_end:
        _conflict("考勤日期不在当前学期范围内")

    query = db.query(AaCalendarEvent).filter(
        AaCalendarEvent.tenant_id == _tid(),
        AaCalendarEvent.term_id == int(term.id),
        AaCalendarEvent.event_type.in_(("HOLIDAY", "SWAP")),
        AaCalendarEvent.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update(read=True)
    rows = query.all()

    holidays = []
    swap_sources = []
    swap_targets = []
    for row in rows:
        event_type = str(getattr(row, "event_type", "") or "").upper()
        start = _date_value(getattr(row, "start_date", None))
        end = _date_value(getattr(row, "end_date", None)) or start
        target = _date_value(getattr(row, "swap_to_date", None))
        if event_type == "HOLIDAY" and start and end and start <= requested <= end:
            holidays.append(row)
        elif event_type == "SWAP":
            if start and end and start <= requested <= end:
                swap_sources.append(row)
            if target and target == requested:
                swap_targets.append(row)

    if swap_sources and swap_targets:
        _conflict("同一日期同时是 SWAP 原停课日和补课日，校历数据冲突")
    if len(swap_targets) > 1:
        _conflict("同一补课日存在多个 SWAP 映射，无法确定正式课次")
    if holidays and swap_targets:
        _conflict("补课日同时被标记为节假日，校历事实冲突")
    if swap_sources:
        _conflict("该日期为校历调休停课日，不能创建普通课堂考勤")
    if holidays:
        _conflict("该日期为节假日，不能创建普通课堂考勤")
    if swap_targets:
        source = _date_value(getattr(swap_targets[0], "start_date", None))
        if not source:
            _conflict("SWAP 缺少原停课日期，无法解析正式课次")
        return source, "SWAP", int(swap_targets[0].id)
    return requested, "NORMAL", None


def _week_and_weekday(term, requested: date) -> tuple[int, int]:
    start = _date_value(getattr(term, "start_date", None))
    end = _date_value(getattr(term, "end_date", None))
    if not start or not end:
        _conflict("当前学期缺少起止日期，不能解析正式课次")
    if requested < start or requested > end:
        _conflict("考勤日期不在当前学期范围内")
    delta = (requested - start).days
    week_no = (delta // 7) + 1
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    if teaching_weeks and week_no > teaching_weeks:
        _conflict("考勤日期超出当前学期教学周范围")
    return week_no, requested.isoweekday()


def _parity_allows(value, week_no: int) -> bool:
    parity = str(value or "ALL").upper()
    if parity == "ALL":
        return True
    if parity == "ODD":
        return week_no % 2 == 1
    if parity == "EVEN":
        return week_no % 2 == 0
    _conflict("正式课表存在未知单双周配置，不能创建考勤")


def _active_heads(db, *, term_id: int, college_id, lock: bool):
    from app.models import AaScheduleScopeHead

    scopes = [("SCHOOL", 0)]
    if college_id:
        scopes.append(("COLLEGE", int(college_id)))
    heads = []
    for scope_type, scope_id in scopes:
        query = db.query(AaScheduleScopeHead).filter(
            AaScheduleScopeHead.tenant_id == _tid(),
            AaScheduleScopeHead.term_id == int(term_id),
            AaScheduleScopeHead.scope_type == scope_type,
            AaScheduleScopeHead.scope_id == int(scope_id),
            AaScheduleScopeHead.is_deleted.is_(False),
        )
        if lock:
            query = query.with_for_update()
        head = query.first()
        if head and head.active_batch_id:
            heads.append(head)
    return heads


def _active_task_schedule(db, task, task_batch, term, *, lock_authority: bool) -> dict:
    """Read the frozen B-C1 active schedule rows for one TeachingTask.

    This is the single shared ScopeHead/PUBLISHED/EFFECTIVE lookup for attendance write
    resolution and attendance read projections. It never creates ScopeHead and never falls
    back to historical EFFECTIVE rows.
    """
    from app.models import AaScheduleBatch, AaScheduleItem

    college_id = int(getattr(task_batch, "college_id", 0) or 0) or None
    heads = _active_heads(
        db,
        term_id=int(term.id),
        college_id=college_id,
        lock=lock_authority,
    )
    active_ids = sorted({int(head.active_batch_id) for head in heads if head.active_batch_id})
    if not active_ids:
        return {
            "status": "NOT_PUBLISHED",
            "issue": "当前学期尚未发布可用于该教学任务的正式课表",
            "heads": heads,
            "activeBatchIds": [],
            "items": [],
        }

    batch_query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == int(term.id),
        AaScheduleBatch.id.in_(active_ids),
        AaScheduleBatch.is_deleted.is_(False),
    )
    if lock_authority:
        batch_query = batch_query.with_for_update(read=True)
    batch_rows = batch_query.all()
    published_ids = {
        int(row.id)
        for row in batch_rows
        if str(getattr(row, "status", "") or "").upper() == "PUBLISHED"
    }
    if published_ids != set(active_ids):
        _conflict("ScopeHead 指向的正式课表批次状态异常，不能消费正式课次")

    task_items = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(active_ids),
        AaScheduleItem.task_id == int(task.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()
    containing_batch_ids = {int(row.batch_id) for row in task_items}
    if len(containing_batch_ids) > 1:
        _conflict(
            "同一教学任务同时出现在多个当前正式课表范围，数据冲突",
            details={
                "teachingTaskId": str(task.id),
                "activeBatchIds": sorted(containing_batch_ids),
            },
        )
    if not task_items:
        return {
            "status": "NOT_SCHEDULED",
            "issue": "当前正式课表中不存在该教学任务的有效课次",
            "heads": heads,
            "activeBatchIds": active_ids,
            "items": [],
        }
    return {
        "status": "READY",
        "issue": "",
        "heads": heads,
        "activeBatchIds": active_ids,
        "items": task_items,
    }


def _validate_task_item_identity(task, item) -> tuple[str, int]:
    task_teacher = str(getattr(task, "teacher_key", "") or "").strip()
    item_teacher = str(getattr(item, "teacher_key", "") or "").strip()
    if not task_teacher or not item_teacher or task_teacher != item_teacher:
        _conflict("正式课表教师身份与教学任务不一致")
    task_class = int(getattr(task, "class_id", 0) or 0)
    item_class = int(getattr(item, "class_id", 0) or 0)
    if task_class and item_class and task_class != item_class:
        _conflict("正式课表班级身份与教学任务不一致")
    task_course = int(getattr(task, "course_id", 0) or 0)
    item_course = int(getattr(item, "course_id", 0) or 0)
    if task_course and item_course and task_course != item_course:
        _conflict("正式课表课程身份与教学任务不一致")
    return item_teacher, item_class


def _validate_linked_change(change, item, task) -> dict:
    if not change:
        _conflict("正式课次回链的调停课单不存在或已删除")
    if str(getattr(change, "status", "") or "").upper() != "APPLIED":
        _conflict("调停课尚未正式生效（APPLIED），不能作为课堂考勤课次")
    change_type = str(getattr(change, "change_type", "") or "").upper()
    if change_type not in {"ADJUST", "MAKEUP"}:
        _conflict("EFFECTIVE 课表项回链了非调课/补课生效单，数据冲突")
    if int(getattr(change, "new_item_id", 0) or 0) != int(item.id):
        _conflict("调停课生效单 newItemId 与正式课次不一致")
    if int(getattr(change, "task_id", 0) or 0) != int(task.id):
        _conflict("调停课生效单教学任务与正式课次不一致")
    if int(getattr(change, "batch_id", 0) or 0) != int(item.batch_id):
        _conflict("调停课生效单课表批次与正式课次不一致")
    if int(getattr(change, "origin_item_id", 0) or 0) == int(item.id):
        _conflict("调停课新课次错误回链原课表项，数据冲突")
    applied_at = getattr(change, "applied_at", None)
    return {
        "changeId": str(change.id),
        "changeType": change_type,
        "changeAppliedAt": applied_at.isoformat() if applied_at else None,
    }


def formal_schedule_patterns_for_tasks(db, task_bindings, term) -> dict[int, dict]:
    """Batch-read current formal recurrence patterns for attendance discovery.

    ``task_bindings`` contains ``(TeachingTask, TeachingTaskBatch)`` pairs already scoped to
    the current tenant/term. The projection never creates ScopeHead, never scans historical
    EFFECTIVE rows, and performs a bounded set of queries regardless of task count. Concrete
    dates remain untrusted until ``resolve_formal_occurrence`` revalidates calendar/change
    truth under write locks.
    """
    from app.models import (
        AaScheduleBatch,
        AaScheduleChange,
        AaScheduleItem,
        AaScheduleScopeHead,
    )

    bindings = {int(task.id): (task, batch) for task, batch in (task_bindings or [])}
    if not bindings:
        return {}

    college_ids = {
        int(getattr(batch, "college_id", 0) or 0)
        for _task, batch in bindings.values()
        if int(getattr(batch, "college_id", 0) or 0)
    }
    head_rows = db.query(AaScheduleScopeHead).filter(
        AaScheduleScopeHead.tenant_id == _tid(),
        AaScheduleScopeHead.term_id == int(term.id),
        AaScheduleScopeHead.scope_type.in_(["SCHOOL", "COLLEGE"]),
        AaScheduleScopeHead.is_deleted.is_(False),
    ).all()
    heads = [
        head for head in head_rows
        if (
            str(head.scope_type or "").upper() == "SCHOOL"
            and int(head.scope_id or 0) == 0
        ) or (
            str(head.scope_type or "").upper() == "COLLEGE"
            and int(head.scope_id or 0) in college_ids
        )
    ]
    active_ids = sorted({int(head.active_batch_id) for head in heads if head.active_batch_id})

    batch_by_id = {}
    if active_ids:
        batch_rows = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.term_id == int(term.id),
            AaScheduleBatch.id.in_(active_ids),
            AaScheduleBatch.is_deleted.is_(False),
        ).all()
        batch_by_id = {int(row.id): row for row in batch_rows}

    item_rows = []
    task_ids = sorted(bindings)
    if active_ids and task_ids:
        item_rows = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _tid(),
            AaScheduleItem.batch_id.in_(active_ids),
            AaScheduleItem.task_id.in_(task_ids),
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        ).all()
    items_by_task = {}
    for item in item_rows:
        items_by_task.setdefault(int(item.task_id), []).append(item)

    change_ids = sorted({int(item.change_id) for item in item_rows if item.change_id})
    change_by_id = {}
    if change_ids:
        change_rows = db.query(AaScheduleChange).filter(
            AaScheduleChange.tenant_id == _tid(),
            AaScheduleChange.id.in_(change_ids),
            AaScheduleChange.is_deleted.is_(False),
        ).all()
        change_by_id = {int(row.id): row for row in change_rows}

    result = {}
    school_heads = [
        head for head in heads
        if str(head.scope_type or "").upper() == "SCHOOL" and int(head.scope_id or 0) == 0
    ]
    for task_id, (task, task_batch) in bindings.items():
        college_id = int(getattr(task_batch, "college_id", 0) or 0)
        relevant_heads = list(school_heads)
        if college_id:
            relevant_heads.extend(
                head for head in heads
                if str(head.scope_type or "").upper() == "COLLEGE"
                and int(head.scope_id or 0) == college_id
            )
        relevant_active_ids = sorted({
            int(head.active_batch_id)
            for head in relevant_heads
            if head.active_batch_id
        })
        if not relevant_active_ids:
            result[task_id] = {
                "status": "NOT_PUBLISHED",
                "issue": "当前学期尚未发布可用于该教学任务的正式课表",
                "patterns": [],
            }
            continue

        bad_active = [
            batch_id for batch_id in relevant_active_ids
            if batch_id not in batch_by_id
            or str(getattr(batch_by_id[batch_id], "status", "") or "").upper() != "PUBLISHED"
        ]
        if bad_active:
            result[task_id] = {
                "status": "CONFLICT",
                "issue": "ScopeHead 指向的正式课表批次状态异常，不能消费正式课次",
                "patterns": [],
            }
            continue

        task_items = [
            row for row in items_by_task.get(task_id, [])
            if int(row.batch_id) in relevant_active_ids
        ]
        containing_batch_ids = {int(row.batch_id) for row in task_items}
        if len(containing_batch_ids) > 1:
            result[task_id] = {
                "status": "CONFLICT",
                "issue": "同一教学任务同时出现在多个当前正式课表范围，数据冲突",
                "patterns": [],
            }
            continue
        if not task_items:
            result[task_id] = {
                "status": "NOT_SCHEDULED",
                "issue": "当前正式课表中不存在该教学任务的有效课次",
                "patterns": [],
            }
            continue

        try:
            patterns = []
            for item in task_items:
                _validate_task_item_identity(task, item)
                matching_heads = [
                    head for head in relevant_heads
                    if int(head.active_batch_id or 0) == int(item.batch_id)
                ]
                if not matching_heads:
                    _conflict("正式课次无法回链当前 ScopeHead，数据冲突")
                matching_heads.sort(key=lambda head: (
                    0 if str(head.scope_type or "").upper() == "COLLEGE" else 1,
                    int(head.scope_id or 0),
                    int(head.id or 0),
                ))
                selected_head = matching_heads[0]
                change_evidence = None
                if item.change_id:
                    change_evidence = _validate_linked_change(
                        change_by_id.get(int(item.change_id)), item, task,
                    )
                patterns.append({
                    "scheduleItemId": str(item.id),
                    "activeBatchId": str(item.batch_id),
                    "scopeType": selected_head.scope_type,
                    "scopeId": str(selected_head.scope_id),
                    "scopeHeadVersion": int(selected_head.version or 0),
                    "weekday": int(item.weekday),
                    "slotNo": int(item.slot_no),
                    "startWeek": int(item.start_week or 0),
                    "endWeek": int(item.end_week or 0),
                    "weekParity": str(item.week_parity or "ALL").upper(),
                    "changeId": change_evidence["changeId"] if change_evidence else None,
                    "changeType": change_evidence["changeType"] if change_evidence else None,
                    "changeAppliedAt": change_evidence["changeAppliedAt"] if change_evidence else None,
                })
            patterns.sort(key=lambda row: (
                int(row["weekday"]),
                int(row["slotNo"]),
                int(row["startWeek"]),
                int(row["scheduleItemId"]),
            ))
            result[task_id] = {"status": "READY", "issue": "", "patterns": patterns}
        except AppException as exc:
            result[task_id] = {
                "status": "CONFLICT",
                "issue": str(getattr(exc, "message", "") or str(exc)),
                "patterns": [],
            }
    return result


def formal_schedule_patterns(db, task, task_batch, term) -> dict:
    return formal_schedule_patterns_for_tasks(db, [(task, task_batch)], term).get(
        int(task.id),
        {"status": "CONFLICT", "issue": "无法读取正式课次投影", "patterns": []},
    )


def _lock_and_validate_selected_item(db, item, task, *, lock: bool):
    """Re-read one EFFECTIVE item with the schedule finalizer-compatible lock order."""
    from app.models import AaScheduleChange, AaScheduleItem

    change_evidence = None
    change_id = int(getattr(item, "change_id", 0) or 0)
    if change_id:
        change_query = db.query(AaScheduleChange).filter(
            AaScheduleChange.id == change_id,
            AaScheduleChange.tenant_id == _tid(),
            AaScheduleChange.is_deleted.is_(False),
        )
        if lock:
            change_query = change_query.with_for_update()
        change = change_query.first()
        change_evidence = _validate_linked_change(change, item, task)

    if lock:
        locked = db.query(AaScheduleItem).filter(
            AaScheduleItem.id == int(item.id),
            AaScheduleItem.tenant_id == _tid(),
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().first()
        if not locked:
            _conflict("正式课次在考勤事务中已失效或删除")
        if str(getattr(locked, "status", "") or "").upper() != "EFFECTIVE":
            _conflict("正式课次已被调停课替换/停止，不能继续创建考勤")
        if int(getattr(locked, "task_id", 0) or 0) != int(task.id):
            _conflict("正式课次教学任务在考勤事务中发生变化")
        if int(getattr(locked, "batch_id", 0) or 0) != int(item.batch_id):
            _conflict("正式课次课表批次在考勤事务中发生变化")
        if int(getattr(locked, "change_id", 0) or 0) != change_id:
            _conflict("正式课次调停课回链在考勤事务中发生变化")
        item = locked
    return item, change_evidence


def resolve_formal_occurrence(
    db,
    task,
    task_batch,
    term,
    *,
    session_date: str,
    slot_no,
    expected_schedule_item_id=None,
    lock: bool = False,
) -> dict:
    """Resolve exactly one current formal occurrence for an attendance write."""
    try:
        requested_slot = int(slot_no)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次") from exc
    if requested_slot <= 0:
        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次")

    expected_item_id = None
    if expected_schedule_item_id not in (None, ""):
        try:
            expected_item_id = int(expected_schedule_item_id)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "scheduleItemId 须为有效数字") from exc
        if expected_item_id <= 0:
            raise AppException("VALIDATION_ERROR", "scheduleItemId 须为有效数字")

    requested = _parse_date(session_date)
    logical_date, calendar_source, calendar_event_id = _calendar_logical_date(
        db,
        term,
        requested,
        lock=lock,
    )
    week_no, weekday = _week_and_weekday(term, logical_date)
    active = _active_task_schedule(
        db, task, task_batch, term, lock_authority=lock,
    )
    if active["status"] != "READY":
        _conflict(active["issue"])
    heads = active["heads"]
    active_ids = active["activeBatchIds"]
    task_items = active["items"]

    candidates = []
    for row in task_items:
        start_week = int(getattr(row, "start_week", 0) or 0)
        end_week = int(getattr(row, "end_week", 0) or 0)
        if int(getattr(row, "weekday", 0) or 0) != weekday:
            continue
        if int(getattr(row, "slot_no", 0) or 0) != requested_slot:
            continue
        if start_week and week_no < start_week:
            continue
        if end_week and week_no > end_week:
            continue
        if not _parity_allows(getattr(row, "week_parity", None), week_no):
            continue
        candidates.append(row)

    if not candidates:
        _conflict("所选日期/节次不是该教学任务当前正式课表中的有效课次")
    if len(candidates) > 1:
        _conflict("同一正式课次命中多条 EFFECTIVE 课表项，数据冲突")

    item = candidates[0]
    item, change_evidence = _lock_and_validate_selected_item(
        db, item, task, lock=lock,
    )
    if expected_item_id is not None and expected_item_id != int(item.id):
        _conflict(
            "正式课次已变化，请刷新后重新进入点名",
            details={
                "expectedScheduleItemId": str(expected_item_id),
                "resolvedScheduleItemId": str(item.id),
                "teachingTaskId": str(task.id),
                "sessionDate": requested.isoformat(),
                "slotNo": requested_slot,
            },
        )
    selected_head = next(
        (head for head in heads if int(head.active_batch_id or 0) == int(item.batch_id)),
        None,
    )
    if not selected_head:
        _conflict("正式课次无法回链当前 ScopeHead，数据冲突")

    item_teacher, item_class = _validate_task_item_identity(task, item)

    published_at = getattr(selected_head, "published_at", None)
    # Canonical concrete occurrence identity stays stable when a republish preserves the same
    # TeachingTask/date/slot. ScheduleItem/batch/ScopeHead versions remain immutable evidence;
    # they must not manufacture a second classroom attendance fact for the same occurrence.
    occurrence_identity = (
        f"V1:TASK:{int(task.id)}:DATE:{requested.isoformat()}:SLOT:{requested_slot}"
    )
    return {
        "sourceType": "FORMAL_TEACHING",
        "occurrenceIdentity": occurrence_identity,
        "termId": str(term.id),
        "scopeType": selected_head.scope_type,
        "scopeId": str(selected_head.scope_id),
        "activeBatchId": str(item.batch_id),
        "scopeHeadVersion": int(selected_head.version or 0),
        "publishedAt": published_at.isoformat() if published_at else None,
        "scheduleItemId": str(item.id),
        "teachingTaskId": str(task.id),
        "sessionDate": requested.isoformat(),
        "logicalDate": logical_date.isoformat(),
        "calendarSource": calendar_source,
        "calendarEventId": str(calendar_event_id) if calendar_event_id else None,
        "weekNo": week_no,
        "weekday": weekday,
        "slotNo": requested_slot,
        "weekParity": str(getattr(item, "week_parity", None) or "ALL").upper(),
        "teacherKey": item_teacher,
        "classId": str(item_class) if item_class else None,
        "changeId": change_evidence["changeId"] if change_evidence else None,
        "changeType": change_evidence["changeType"] if change_evidence else None,
        "changeAppliedAt": change_evidence["changeAppliedAt"] if change_evidence else None,
    }
