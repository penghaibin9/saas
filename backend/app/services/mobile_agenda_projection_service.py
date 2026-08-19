"""V3 §6 学生「今天 / 未来 7 天」移动 Agenda 投影。

**它是纯读投影**：把已经分散在教务、学工、实习等域里的时间事实，按时间窗聚合成一条
时间线。它不是新的业务表，也**不允许成为新的 deadline 真值**——每条 item 都必须能回指
到它真正的来源记录（sourceModule / sourceBizType / sourceBizId）。

三条硬约束（§6.2）：

1. 只查时间窗内的数据。禁止把全学期课表或全部历史业务读进 Python 再筛。
2. 课程/考试消费教务已有的校历真值：周次由
   :func:`academic_affairs_teacher_relation_authority.teaching_week_for_date` 解析，
   本模块不复制任何周次算法。
3. 同一时刻的事件不做跨域状态合并，只按优先级排序；冲突提示属于展示，不改业务真值。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.services import mobile_action_service as action_svc
from app.services.db_service import _iso, _tid, session

#: 默认时间窗（天）。首页只取前 3 条，Agenda 页首屏 20 条。
DEFAULT_DAYS = 7
MAX_DAYS = 14
HOME_TODAY_LIMIT = 3
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 50

#: 排序优先级：同一时刻先看考试，再看截止，最后看课程。
_KIND_PRIORITY = {"EXAM": 0, "DEADLINE": 1, "COURSE": 2, "OTHER": 3}


def _local_today() -> date:
    return datetime.now().date()


def _window(days: int | None) -> tuple[date, date]:
    # 只有「没传」才用默认 7 天；显式传 0/负数是调用方的错，夹到 1 天，
    # 不能用 `days or DEFAULT` 把 0 悄悄放大成 7 天的扫描范围。
    requested = DEFAULT_DAYS if days is None else int(days)
    span = max(1, min(MAX_DAYS, requested))
    start = _local_today()
    return start, start + timedelta(days=span - 1)


def _combine(day: date, hhmm: str | None) -> str:
    """把 YYYY-MM-DD + HH:MM 拼成本地 ISO 时间；没有钟点就落在当天 00:00。"""
    parsed = time(0, 0)
    if hhmm and ":" in str(hhmm):
        try:
            hour, minute = str(hhmm).split(":")[:2]
            parsed = time(int(hour), int(minute))
        except (TypeError, ValueError):
            parsed = time(0, 0)
    return datetime.combine(day, parsed).isoformat(timespec="seconds")


def _status_for(start_at: str) -> str:
    """UPCOMING / ONGOING / PAST 只按服务器时间判定，不接受客户端时间。"""
    try:
        started = datetime.fromisoformat(start_at)
    except ValueError:
        return "UPCOMING"
    now = datetime.now()
    if started.date() == now.date() and started <= now:
        return "ONGOING"
    return "PAST" if started < now else "UPCOMING"


# ── 来源 1：业务截止（UnifiedTodo.due_at 落在窗口内） ──

def _deadline_items(db, user: dict, student_id: int, start: date, end: date) -> list[dict[str, Any]]:
    from app.models import UnifiedTodo
    from app.services.todo_route_registry import resolve_todo_route

    window_start = datetime.combine(start, time(0, 0), tzinfo=timezone.utc) - timedelta(days=1)
    window_end = datetime.combine(end, time(23, 59, 59), tzinfo=timezone.utc) + timedelta(days=1)
    rows = db.scalars(
        select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.student_id == student_id,
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.due_at.is_not(None),
            UnifiedTodo.due_at >= window_start,
            UnifiedTodo.due_at <= window_end,
        ).order_by(UnifiedTodo.due_at.asc(), UnifiedTodo.id.asc()).limit(100)
    ).all()

    items = []
    for row in rows:
        due = row.due_at
        if not due or not (start <= due.date() <= end):
            continue
        record_id = str(row.source_biz_id) if row.source_biz_id else None
        route = resolve_todo_route(row.todo_type, record_id, client=action_svc.CLIENT_STUDENT_MINI)
        todo_dto = {
            "todoType": row.todo_type,
            "recordId": record_id,
            "bizType": row.source_biz_type,
            "title": row.title,
            "allowedActions": ["OPEN"] if route else [],
            "version": int(getattr(row, "version", 0) or 0),
        }
        items.append({
            "eventId": f"todo:{row.id}",
            "sourceModule": row.source_module or "待办",
            "sourceBizType": row.source_biz_type or row.todo_type,
            "sourceBizId": record_id,
            "title": row.title or "待办事项",
            "startAt": _iso(due),
            "endAt": None,
            "kind": "DEADLINE",
            "priority": "HIGH" if due.date() == start else "NORMAL",
            "location": None,
            "action": action_svc.build_todo_action(todo_dto, client=action_svc.CLIENT_STUDENT_MINI),
        })
    return items


# ── 来源 2：考试（本人已排考座位，exam_date 落在窗口内） ──

def _exam_items(db, student_id: int, start: date, end: date) -> list[dict[str, Any]]:
    from app.models import AaExamCourse, AaExamRoom, AaExamRoomStudent

    rows = db.execute(
        select(
            AaExamCourse.id, AaExamCourse.course_name, AaExamCourse.exam_date,
            AaExamCourse.start_time, AaExamCourse.end_time,
            AaExamRoom.classroom_text, AaExamRoomStudent.seat_no,
        )
        .join(AaExamRoomStudent, AaExamRoomStudent.exam_course_id == AaExamCourse.id)
        .join(AaExamRoom, AaExamRoom.id == AaExamRoomStudent.exam_room_id)
        .where(
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.is_deleted.is_(False),
            AaExamCourse.status == "CONFIRMED",
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.student_id == int(student_id),
            AaExamRoomStudent.is_deleted.is_(False),
            # exam_date 是 YYYY-MM-DD 文本列，字典序与日期序一致，因此可以直接做区间下推，
            # 不需要把全批次考试读进 Python 再筛。
            AaExamCourse.exam_date >= start.isoformat(),
            AaExamCourse.exam_date <= end.isoformat(),
        ).order_by(AaExamCourse.exam_date.asc(), AaExamCourse.start_time.asc()).limit(100)
    ).all()

    items = []
    for row in rows:
        try:
            day = date.fromisoformat(str(row.exam_date))
        except (TypeError, ValueError):
            continue
        items.append({
            "eventId": f"academic-exam:{row.id}:{row.exam_date}",
            "sourceModule": "academic",
            "sourceBizType": "EXAM",
            "sourceBizId": str(row.id),
            "title": row.course_name or "考试",
            "startAt": _combine(day, row.start_time),
            "endAt": _combine(day, row.end_time) if row.end_time else None,
            "kind": "EXAM",
            "priority": "HIGH",
            "location": row.classroom_text,
            "seatNo": row.seat_no,
            # 考试详情页当前不消费 examId（学生端考试页是列表），Adapter 会据此返回 NONE，
            # 不虚报对象级闭环。
            "action": action_svc.build_message_action(
                "student.exam.detail", {"examId": str(row.id)},
                client=action_svc.CLIENT_STUDENT_MINI,
            ),
        })
    return items


# ── 来源 3：课程（消费教务校历真值解析周次，不复制周次算法） ──

def _course_items(db, student, start: date, end: date) -> list[dict[str, Any]]:
    from app.models import AaScheduleBatch, AaScheduleItem, AaTimeSlot
    from app.modules.academic_affairs.services.academic_affairs_teacher_relation_authority import (
        teaching_week_for_date,
    )

    class_id = getattr(student, "class_id", None)
    if not class_id:
        return []
    batch = db.scalars(
        select(AaScheduleBatch).where(
            AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.status == "PUBLISHED",
            AaScheduleBatch.is_deleted.is_(False),
        ).order_by(AaScheduleBatch.id.desc())
    ).first()
    if not batch:
        return []

    # 先把窗口内每一天解析成教学周（校历真值），得到 (日期, 周次, 星期) 三元组。
    days: list[tuple[date, int, int]] = []
    cursor = start
    while cursor <= end:
        week = teaching_week_for_date(db, int(batch.term_id), cursor)
        if week:
            days.append((cursor, int(week), cursor.isoweekday()))
        cursor += timedelta(days=1)
    if not days:
        return []

    weeks = {week for _, week, _ in days}
    weekdays = {weekday for _, _, weekday in days}
    rows = db.scalars(
        select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(),
            AaScheduleItem.batch_id == int(batch.id),
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
            AaScheduleItem.class_id == int(class_id),
            # 只取窗口内可能命中的星期与周次区间，不读全学期。
            AaScheduleItem.weekday.in_(sorted(weekdays)),
            AaScheduleItem.start_week <= max(weeks),
            AaScheduleItem.end_week >= min(weeks),
        ).order_by(AaScheduleItem.weekday.asc(), AaScheduleItem.slot_no.asc()).limit(200)
    ).all()
    if not rows:
        return []

    slots = {
        slot.slot_no: slot
        for slot in db.scalars(
            select(AaTimeSlot).where(
                AaTimeSlot.tenant_id == _tid(),
                AaTimeSlot.is_deleted.is_(False),
                AaTimeSlot.slot_no.in_(sorted({row.slot_no for row in rows})),
            )
        ).all()
    }

    items = []
    for day, week, weekday in days:
        for row in rows:
            if row.weekday != weekday:
                continue
            if not (int(row.start_week) <= week <= int(row.end_week)):
                continue
            parity = str(row.week_parity or "ALL").upper()
            if parity == "ODD" and week % 2 == 0:
                continue
            if parity == "EVEN" and week % 2 == 1:
                continue
            slot = slots.get(row.slot_no)
            items.append({
                "eventId": f"academic-course:{row.id}:{day.isoformat()}",
                "sourceModule": "academic",
                "sourceBizType": "COURSE",
                "sourceBizId": str(row.id),
                "title": row.course_name or "课程",
                "startAt": _combine(day, getattr(slot, "start_time", None)),
                "endAt": _combine(day, getattr(slot, "end_time", None)) if slot else None,
                "kind": "COURSE",
                "priority": "NORMAL",
                "location": row.classroom_text,
                "teacherName": row.teacher_name,
                # 课程本身没有可办理动作；课表页是安全入口，交给 quickServices，不在这里造 action。
                "action": None,
            })
    return items


def _cursor_of(item: dict[str, Any]) -> str:
    """keyset 游标 = 排序键本身（startAt|eventId），单调且唯一，翻页不漏不重。"""
    return f"{item.get('startAt') or ''}|{item.get('eventId') or ''}"


def _sort_key(item: dict[str, Any]) -> tuple:
    return (
        str(item.get("startAt") or ""),
        _KIND_PRIORITY.get(str(item.get("kind") or "OTHER"), 9),
        str(item.get("eventId") or ""),
    )


def list_student_agenda(user: dict, *, days: int = DEFAULT_DAYS, cursor: str | None = None,
                        page_size: int = PAGE_SIZE_DEFAULT) -> dict[str, Any]:
    """未来 N 天的纯读时间线。cursor 是上一页最后一条的排序键，避免深 OFFSET。"""
    from app.db.session import db_enabled
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    if not db_enabled():
        return {"items": [], "nextCursor": None, "days": DEFAULT_DAYS, "hasData": False}

    size = max(1, min(PAGE_SIZE_MAX, int(page_size or PAGE_SIZE_DEFAULT)))
    start, end = _window(days)
    with session() as db:
        student = resolve_student(db, current)
        if not student:
            return {"items": [], "nextCursor": None, "days": DEFAULT_DAYS, "hasData": False}
        items = (
            _deadline_items(db, current, student.id, start, end)
            + _exam_items(db, student.id, start, end)
            + _course_items(db, student, start, end)
        )

    items.sort(key=_sort_key)
    for item in items:
        item["status"] = _status_for(str(item.get("startAt") or ""))

    if cursor:
        items = [item for item in items if _cursor_of(item) > str(cursor)]
    page = items[:size]
    has_more = len(items) > size
    next_cursor = _cursor_of(page[-1]) if has_more and page else None
    return {
        "items": page,
        "nextCursor": next_cursor,
        "days": (end - start).days + 1,
        "windowStart": start.isoformat(),
        "windowEnd": end.isoformat(),
        "hasData": True,
    }


def today_for_home(user: dict) -> list[dict[str, Any]]:
    """首页「今天」只取前 3 条，且只取今天当天的事件（§5.1）。"""
    today = _local_today().isoformat()
    try:
        data = list_student_agenda(user, days=1, page_size=HOME_TODAY_LIMIT)
    except Exception:  # noqa: BLE001
        # 首页是聚合投影：单个域读失败不应让整张首页 500，缺这一块比整页打不开好。
        return []
    return [item for item in data.get("items", []) if str(item.get("startAt", "")).startswith(today)][:HOME_TODAY_LIMIT]


def agenda_contract_snapshot() -> dict[str, Any]:
    return {
        "defaultDays": DEFAULT_DAYS,
        "maxDays": MAX_DAYS,
        "pageSizeDefault": PAGE_SIZE_DEFAULT,
        "pageSizeMax": PAGE_SIZE_MAX,
        "homeTodayLimit": HOME_TODAY_LIMIT,
        "kinds": sorted(_KIND_PRIORITY),
        "sources": ["UnifiedTodo.due_at", "AaExamRoomStudent+AaExamCourse.exam_date", "AaScheduleItem+校历周次"],
    }
