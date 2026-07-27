"""V2 PageId AA-TERM-01 学期详情、影响预览与安全修改。

复用 AaTerm 与既有审计流水；不建立第二套学期事实。
发布后禁止直接修改时间轴，先返回课表、考试、选课、成绩等真实关联影响。
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

from . import academic_affairs_service as _base


_STRUCTURAL_FIELDS = {
    "startDate": "开学日期",
    "endDate": "结束日期",
    "teachingWeeks": "教学周数",
    "examWeekStart": "考试周开始周次",
}

_ACTION_LABELS = {
    "CREATE": "创建学期",
    "UPDATE_BASIC": "修改基本信息",
    "PUBLISH": "发布学期",
    "SET_CURRENT": "设为当前学期",
    "FREEZE": "冻结学期",
    "ARCHIVE": "归档学期",
}


def _to_datetime(value, *, end_of_day=False):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.max if end_of_day else time.min)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"日期格式非法：{value}") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _term(db, term_id, *, lock=False):
    from app.models import AaTerm

    query = select(AaTerm).where(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = db.scalars(query).first()
    if not row:
        raise not_found("学期不存在")
    return row


def _count_by_status(rows) -> dict:
    return dict(sorted(Counter(str(getattr(row, "status", None) or "UNKNOWN") for row in rows).items()))


def _linked_data(db, term) -> dict:
    from app.models import (
        AaCalendarEvent,
        AaExamBatch,
        AaExamCourse,
        AaGradeTask,
        AaScheduleBatch,
        AaScheduleItem,
        AaSelectionBatch,
        AaSelectionCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
    )

    calendar_count = db.scalar(select(func.count()).select_from(AaCalendarEvent).where(
        AaCalendarEvent.tenant_id == _tid(),
        AaCalendarEvent.term_id == term.id,
        AaCalendarEvent.is_deleted.is_(False),
    )) or 0

    task_batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == term.id,
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    task_batch_ids = [int(row.id) for row in task_batches]
    task_count = db.scalar(select(func.count()).select_from(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [0]),
        AaTeachingTask.is_deleted.is_(False),
    )) or 0

    schedule_batches = db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == _tid(),
        AaScheduleBatch.term_id == term.id,
        AaScheduleBatch.is_deleted.is_(False),
    )).all()
    schedule_batch_ids = [int(row.id) for row in schedule_batches]
    schedule_item_count = db.scalar(select(func.count()).select_from(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(schedule_batch_ids or [0]),
        AaScheduleItem.is_deleted.is_(False),
    )) or 0

    exam_batches = db.scalars(select(AaExamBatch).where(
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.term_id == term.id,
        AaExamBatch.is_deleted.is_(False),
    )).all()
    exam_batch_ids = [int(row.id) for row in exam_batches]
    exam_course_count = db.scalar(select(func.count()).select_from(AaExamCourse).where(
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.batch_id.in_(exam_batch_ids or [0]),
        AaExamCourse.is_deleted.is_(False),
    )) or 0

    selection_batches = db.scalars(select(AaSelectionBatch).where(
        AaSelectionBatch.tenant_id == _tid(),
        AaSelectionBatch.term_id == term.id,
        AaSelectionBatch.is_deleted.is_(False),
    )).all()
    selection_batch_ids = [int(row.id) for row in selection_batches]
    selection_course_count = db.scalar(select(func.count()).select_from(AaSelectionCourse).where(
        AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.batch_id.in_(selection_batch_ids or [0]),
        AaSelectionCourse.is_deleted.is_(False),
    )) or 0

    grade_tasks = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == _tid(),
        (
            (AaGradeTask.term_id == term.id)
            | (AaGradeTask.term_code == f"{term.year_code}-{term.term_no}")
        ),
        AaGradeTask.is_deleted.is_(False),
    )).all()

    return {
        "calendar": {"count": int(calendar_count), "route": f"/admin/academic-affairs/calendar?termId={term.id}"},
        "teachingTasks": {
            "batchCount": len(task_batches), "recordCount": int(task_count),
            "statusCounts": _count_by_status(task_batches),
            "route": f"/admin/academic-affairs/teaching-tasks?termId={term.id}",
        },
        "schedules": {
            "batchCount": len(schedule_batches), "recordCount": int(schedule_item_count),
            "statusCounts": _count_by_status(schedule_batches),
            "route": f"/admin/academic-affairs/scheduling?termId={term.id}",
        },
        "exams": {
            "batchCount": len(exam_batches), "recordCount": int(exam_course_count),
            "statusCounts": _count_by_status(exam_batches),
            "route": f"/admin/academic-affairs/exam?termId={term.id}",
        },
        "selections": {
            "batchCount": len(selection_batches), "recordCount": int(selection_course_count),
            "statusCounts": _count_by_status(selection_batches),
            "route": f"/admin/academic-affairs/selection?termId={term.id}",
        },
        "grades": {
            "count": len(grade_tasks), "statusCounts": _count_by_status(grade_tasks),
            "route": f"/admin/academic-affairs/grade-tasks?termId={term.id}",
        },
    }


def _timeline(db, term_id) -> list[dict]:
    from app.models import AffairsAuditTrail

    rows = db.scalars(select(AffairsAuditTrail).where(
        AffairsAuditTrail.tenant_id == _tid(),
        AffairsAuditTrail.biz_type == "AA_TERM",
        AffairsAuditTrail.biz_id == int(term_id),
        AffairsAuditTrail.is_deleted.is_(False),
    ).order_by(AffairsAuditTrail.occurred_at.desc(), AffairsAuditTrail.id.desc())).all()
    return [{
        "auditId": str(row.id),
        "action": row.action,
        "actionLabel": _ACTION_LABELS.get(row.action, row.action),
        "operator": row.operator or "系统",
        "roleName": row.role_name or "",
        "detail": row.detail or "",
        "occurredAt": _iso(row.occurred_at),
    } for row in rows]


def _allowed_actions(term, linked) -> dict:
    status = str(term.status or "").upper()
    has_linked = any([
        linked["calendar"]["count"],
        linked["teachingTasks"]["recordCount"],
        linked["schedules"]["recordCount"],
        linked["exams"]["recordCount"],
        linked["selections"]["recordCount"],
        linked["grades"]["count"],
    ])
    return {
        "editBasic": status == "DRAFT",
        "editNameOnly": status in {"PUBLISHED", "FROZEN"},
        "publish": status == "DRAFT",
        "setCurrent": status in {"PUBLISHED", "FROZEN"} and not bool(term.is_current),
        "freeze": status == "PUBLISHED",
        "archive": status == "FROZEN",
        "viewImpact": True,
        "hasLinkedBusiness": bool(has_linked),
    }


def term_detail(term_id, user) -> dict:
    """原 GET /terms/{termId} 的最终实现。"""
    with session() as db:
        term = _term(db, term_id)
        linked = _linked_data(db, term)
        allowed = _allowed_actions(term, linked)
        return {
            **_base._term_row(term),
            "version": int(getattr(term, "version", 0) or 0),
            "linkedData": linked,
            "allowedActions": allowed,
            "impactWarning": (
                "该学期已经产生关联业务。修改时间轴会影响课表周次、考试日期、选课窗口和成绩收口，必须先查看影响。"
                if allowed["hasLinkedBusiness"] else
                "当前尚无关联业务，草稿状态可直接维护基础时间轴。"
            ),
            "timeline": _timeline(db, term.id),
            "archiveRoute": f"/admin/academic-affairs/archive/precheck?termId={term.id}",
        }


def _proposed(term, body: dict) -> dict:
    data = body or {}
    return {
        "termName": str(data.get("termName") if "termName" in data else (term.term_name or "")).strip(),
        "startDate": _to_datetime(data.get("startDate"), end_of_day=False) if "startDate" in data else term.start_date,
        "endDate": _to_datetime(data.get("endDate"), end_of_day=True) if "endDate" in data else term.end_date,
        "teachingWeeks": int(data.get("teachingWeeks")) if data.get("teachingWeeks") not in (None, "") else term.teaching_weeks,
        "examWeekStart": int(data.get("examWeekStart")) if data.get("examWeekStart") not in (None, "") else term.exam_week_start,
    }


def _validate_proposed(proposed: dict) -> None:
    start, end = proposed["startDate"], proposed["endDate"]
    if start and end and start > end:
        raise AppException("VALIDATION_ERROR", "开学日期不得晚于学期结束日期")
    weeks = proposed["teachingWeeks"]
    exam_week = proposed["examWeekStart"]
    if weeks is not None and not 1 <= int(weeks) <= 30:
        raise AppException("VALIDATION_ERROR", "教学周数必须在1—30周")
    if exam_week is not None and not 1 <= int(exam_week) <= int(weeks or 30):
        raise AppException("VALIDATION_ERROR", "考试周开始周次必须落在教学周数范围内")


def _changes(term, proposed) -> list[dict]:
    current = {
        "termName": term.term_name or "",
        "startDate": term.start_date,
        "endDate": term.end_date,
        "teachingWeeks": term.teaching_weeks,
        "examWeekStart": term.exam_week_start,
    }
    rows = []
    labels = {"termName": "学期名称", **_STRUCTURAL_FIELDS}
    for field, after in proposed.items():
        before = current[field]
        before_cmp = _iso(before)[:10] if before and field in {"startDate", "endDate"} else before
        after_cmp = _iso(after)[:10] if after and field in {"startDate", "endDate"} else after
        if before_cmp != after_cmp:
            rows.append({"field": field, "label": labels[field], "before": before_cmp, "after": after_cmp})
    return rows


def impact_preview(term_id, user, body: dict | None = None) -> dict:
    """修改前影响预览；只读，不落库。"""
    from app.models import AaCalendarEvent, AaExamBatch, AaExamCourse, AaScheduleBatch, AaScheduleItem, AaSelectionBatch

    with session() as db:
        term = _term(db, term_id)
        proposed = _proposed(term, body or {})
        _validate_proposed(proposed)
        changes = _changes(term, proposed)
        structural = [row for row in changes if row["field"] in _STRUCTURAL_FIELDS]
        linked = _linked_data(db, term)

        schedule_batch_ids = [value for (value,) in db.query(AaScheduleBatch.id).filter(
            AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.term_id == term.id,
            AaScheduleBatch.is_deleted.is_(False),
        ).all()]
        schedule_over_week = 0
        if proposed["teachingWeeks"]:
            schedule_over_week = db.query(AaScheduleItem).filter(
                AaScheduleItem.tenant_id == _tid(),
                AaScheduleItem.batch_id.in_(schedule_batch_ids or [0]),
                AaScheduleItem.end_week > int(proposed["teachingWeeks"]),
                AaScheduleItem.is_deleted.is_(False),
            ).count()

        start_date = proposed["startDate"].date() if proposed["startDate"] else None
        end_date = proposed["endDate"].date() if proposed["endDate"] else None
        calendar_outside = 0
        events = db.query(AaCalendarEvent).filter(
            AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == term.id,
            AaCalendarEvent.is_deleted.is_(False),
        ).all()
        for event in events:
            event_start = event.start_date.date() if isinstance(event.start_date, datetime) else event.start_date
            event_end = event.end_date.date() if isinstance(event.end_date, datetime) else event.end_date
            if (start_date and event_start and event_start < start_date) or (end_date and event_end and event_end > end_date):
                calendar_outside += 1

        exam_batch_ids = [value for (value,) in db.query(AaExamBatch.id).filter(
            AaExamBatch.tenant_id == _tid(), AaExamBatch.term_id == term.id,
            AaExamBatch.is_deleted.is_(False),
        ).all()]
        exam_outside = 0
        exam_rows = db.query(AaExamCourse).filter(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id.in_(exam_batch_ids or [0]),
            AaExamCourse.is_deleted.is_(False),
        ).all()
        for course in exam_rows:
            try:
                exam_date = date.fromisoformat(str(course.exam_date)[:10]) if course.exam_date else None
            except ValueError:
                exam_date = None
            if (start_date and exam_date and exam_date < start_date) or (end_date and exam_date and exam_date > end_date):
                exam_outside += 1

        selection_windows_outside = 0
        selection_rows = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.term_id == term.id,
            AaSelectionBatch.is_deleted.is_(False),
        ).all()
        for batch in selection_rows:
            select_start = batch.select_start_at.date() if isinstance(batch.select_start_at, datetime) else batch.select_start_at
            select_end = batch.select_end_at.date() if isinstance(batch.select_end_at, datetime) else batch.select_end_at
            if (start_date and select_start and select_start < start_date) or (end_date and select_end and select_end > end_date):
                selection_windows_outside += 1

        impact_items = [
            {
                "domain": "CALENDAR", "label": "校历",
                "affectedCount": linked["calendar"]["count"],
                "conflictCount": calendar_outside,
                "summary": f"关联校历事件 {linked['calendar']['count']} 条，其中 {calendar_outside} 条超出拟调整日期范围。",
                "route": linked["calendar"]["route"],
            },
            {
                "domain": "SCHEDULE", "label": "课表",
                "affectedCount": linked["schedules"]["recordCount"],
                "conflictCount": schedule_over_week,
                "summary": f"关联课表项 {linked['schedules']['recordCount']} 条，其中 {schedule_over_week} 条结束周次超过拟调整教学周数。",
                "route": linked["schedules"]["route"],
            },
            {
                "domain": "EXAM", "label": "考试",
                "affectedCount": linked["exams"]["recordCount"],
                "conflictCount": exam_outside,
                "summary": f"关联考试课程 {linked['exams']['recordCount']} 门，其中 {exam_outside} 门考试日期超出拟调整日期范围。",
                "route": linked["exams"]["route"],
            },
            {
                "domain": "SELECTION", "label": "选课",
                "affectedCount": linked["selections"]["batchCount"],
                "conflictCount": selection_windows_outside,
                "summary": f"关联选课批次 {linked['selections']['batchCount']} 个，其中 {selection_windows_outside} 个选课窗口超出拟调整日期范围。",
                "route": linked["selections"]["route"],
            },
            {
                "domain": "GRADE", "label": "成绩",
                "affectedCount": linked["grades"]["count"],
                "conflictCount": 0,
                "summary": f"关联成绩任务 {linked['grades']['count']} 个；时间轴变化会改变录入、审核和归档截止口径。",
                "route": linked["grades"]["route"],
            },
        ]
        conflict_count = sum(int(row["conflictCount"] or 0) for row in impact_items)
        status = str(term.status or "").upper()
        direct_change_allowed = status == "DRAFT"
        blockers = []
        if structural and not direct_change_allowed:
            blockers.append({
                "code": "TERM_PUBLISHED_DIRECT_CHANGE_FORBIDDEN",
                "message": f"当前状态为 {status}，禁止直接修改学期时间轴。请先处理关联业务并走正式变更流程。",
            })
        if conflict_count:
            blockers.append({
                "code": "TERM_CHANGE_LINKED_CONFLICTS",
                "message": f"拟调整方案与 {conflict_count} 条现有业务事实冲突。",
            })
        return {
            "termId": str(term.id),
            "termStatus": term.status,
            "version": int(getattr(term, "version", 0) or 0),
            "changes": changes,
            "structuralChange": bool(structural),
            "directChangeAllowed": direct_change_allowed,
            "canSave": bool(changes) and direct_change_allowed and conflict_count == 0,
            "blockerCount": len(blockers),
            "conflictCount": conflict_count,
            "blockers": blockers,
            "impacts": impact_items,
            "conclusion": (
                "草稿学期可以直接保存本次修改。" if changes and direct_change_allowed and conflict_count == 0
                else "当前修改不可直接保存，请先处理影响或保持原时间轴。"
                if changes else "未检测到字段变化。"
            ),
        }


def update_term(term_id, user, body: dict) -> dict:
    """草稿学期安全修改；已发布/冻结只允许改显示名称。"""
    with session() as db:
        term = _term(db, term_id, lock=True)
        expected = body.get("expectedVersion")
        if expected is not None and int(expected) != int(getattr(term, "version", 0) or 0):
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "学期信息已被其他人修改，请刷新后重试",
                details={"currentVersion": int(getattr(term, "version", 0) or 0)},
                http_status=409,
            )
        proposed = _proposed(term, body)
        _validate_proposed(proposed)
        changes = _changes(term, proposed)
        if not changes:
            return term_detail(term.id, user)
        structural = [row for row in changes if row["field"] in _STRUCTURAL_FIELDS]
        if structural and str(term.status or "").upper() != "DRAFT":
            preview = impact_preview(term.id, user, body)
            raise AppException(
                "DATA_CONFLICT",
                "已发布或冻结学期禁止直接修改日期、教学周数和考试周，请先查看影响预览",
                details=preview,
                http_status=409,
            )
        if str(term.status or "").upper() == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档学期只读，不可修改", http_status=409)

        before = ";".join(f"{row['label']}={row['before']}" for row in changes)
        after = ";".join(f"{row['label']}={row['after']}" for row in changes)
        term.term_name = proposed["termName"] or term.term_name
        if not structural or str(term.status or "").upper() == "DRAFT":
            term.start_date = proposed["startDate"]
            term.end_date = proposed["endDate"]
            term.teaching_weeks = proposed["teachingWeeks"]
            term.exam_week_start = proposed["examWeekStart"]
        term.version = int(getattr(term, "version", 0) or 0) + 1
        _base._audit(db, "AA_TERM", term.id, "UPDATE_BASIC", f"{before} -> {after}")
        db.commit()
        return term_detail(term.id, user)


# 现有 GET /terms/{termId} 直接获得完整详情。
_base.term_detail = term_detail
