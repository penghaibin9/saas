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


def resolve_formal_occurrence(
    db,
    task,
    task_batch,
    term,
    *,
    session_date: str,
    slot_no,
    lock: bool = False,
) -> dict:
    """Resolve exactly one current formal occurrence for an attendance write."""
    from app.models import AaScheduleBatch, AaScheduleItem

    try:
        requested_slot = int(slot_no)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次") from exc
    if requested_slot <= 0:
        raise AppException("VALIDATION_ERROR", "普通课堂必须选择明确节次")

    requested = _parse_date(session_date)
    week_no, weekday = _week_and_weekday(term, requested)
    college_id = int(getattr(task_batch, "college_id", 0) or 0) or None
    heads = _active_heads(
        db,
        term_id=int(term.id),
        college_id=college_id,
        lock=lock,
    )
    active_ids = sorted({int(head.active_batch_id) for head in heads if head.active_batch_id})
    if not active_ids:
        _conflict("当前学期尚未发布可用于该教学任务的正式课表")

    batch_query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == int(term.id),
        AaScheduleBatch.id.in_(active_ids),
        AaScheduleBatch.is_deleted.is_(False),
    )
    if lock:
        batch_query = batch_query.with_for_update(read=True)
    batch_rows = batch_query.all()
    published_ids = {
        int(row.id)
        for row in batch_rows
        if str(getattr(row, "status", "") or "").upper() == "PUBLISHED"
    }
    if published_ids != set(active_ids):
        _conflict("ScopeHead 指向的正式课表批次状态异常，不能创建考勤")

    item_query = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(active_ids),
        AaScheduleItem.task_id == int(task.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    )
    if lock:
        item_query = item_query.with_for_update()
    task_items = item_query.all()
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
        _conflict("当前正式课表中不存在该教学任务的有效课次")

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
    selected_head = next(
        (head for head in heads if int(head.active_batch_id or 0) == int(item.batch_id)),
        None,
    )
    if not selected_head:
        _conflict("正式课次无法回链当前 ScopeHead，数据冲突")

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

    published_at = getattr(selected_head, "published_at", None)
    return {
        "sourceType": "FORMAL_TEACHING",
        "termId": str(term.id),
        "scopeType": selected_head.scope_type,
        "scopeId": str(selected_head.scope_id),
        "activeBatchId": str(item.batch_id),
        "scopeHeadVersion": int(selected_head.version or 0),
        "publishedAt": published_at.isoformat() if published_at else None,
        "scheduleItemId": str(item.id),
        "teachingTaskId": str(task.id),
        "sessionDate": requested.isoformat(),
        "weekNo": week_no,
        "weekday": weekday,
        "slotNo": requested_slot,
        "weekParity": str(getattr(item, "week_parity", None) or "ALL").upper(),
        "teacherKey": item_teacher,
        "classId": str(item_class) if item_class else None,
    }
