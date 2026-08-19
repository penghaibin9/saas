"""C-W2 Teacher Today read-only work cues.

Only consumes mature Exam invigilation facts and the canonical AA_GRADE_ENTRY UnifiedTodo.
Rendering Teacher Today must never create, refresh, or repair either authority.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.services.db_service import _tid

_GRADE_TODO = "AA_GRADE_ENTRY"
_GRADE_ROUTE = "/pages/teacher/academic-affairs/grade-entry"


def _user_keys(user) -> set[str]:
    return {str(value).strip() for value in _derive_keys(user or {}) if str(value).strip()}


def _resolve_user_id(db, user) -> int | None:
    """Resolve the current real User.id by stable id/login facts; read only, no fallback creation."""
    from app.models import User

    raw = str((user or {}).get("userId") or "").strip()
    numeric = raw[3:] if raw.startswith("db-") else raw[2:] if raw.startswith("u_") else raw
    if numeric.isdigit():
        row = db.get(User, int(numeric))
        if row and not row.is_deleted and row.tenant_id == _tid() and row.status == "ACTIVE":
            return int(row.id)
    login = str((user or {}).get("loginName") or "").strip()
    if login:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(),
            User.login_name == login,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )).first()
        if row:
            return int(row.id)
    return None


def today_invigilations(db, user, *, exam_date: str) -> list[dict]:
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    keys = sorted(_user_keys(user))
    if not keys:
        return []
    invigilators = db.scalars(select(AaExamInvigilator).where(
        AaExamInvigilator.tenant_id == _tid(),
        AaExamInvigilator.teacher_key.in_(keys),
        AaExamInvigilator.is_deleted.is_(False),
    )).all()
    room_ids = sorted({int(row.exam_room_id) for row in invigilators if row.exam_room_id})
    if not room_ids:
        return []
    rooms = db.scalars(select(AaExamRoom).where(
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.id.in_(room_ids),
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    )).all()
    room_by_id = {int(row.id): row for row in rooms}
    course_ids = sorted({int(row.exam_course_id) for row in rooms if row.exam_course_id})
    courses = []
    if course_ids:
        courses = db.scalars(select(AaExamCourse).where(
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.id.in_(course_ids),
            AaExamCourse.exam_date == str(exam_date),
            AaExamCourse.status == "CONFIRMED",
            AaExamCourse.is_deleted.is_(False),
        )).all()
    course_by_id = {int(row.id): row for row in courses}
    batch_ids = sorted({int(row.batch_id) for row in courses if row.batch_id})
    batches = []
    if batch_ids:
        batches = db.scalars(select(AaExamBatch).where(
            AaExamBatch.tenant_id == _tid(),
            AaExamBatch.id.in_(batch_ids),
            AaExamBatch.status == "PUBLISHED",
            AaExamBatch.is_deleted.is_(False),
        )).all()
    published_batch_ids = {int(row.id) for row in batches}

    output = []
    for invigilator in invigilators:
        room = room_by_id.get(int(invigilator.exam_room_id or 0))
        course = course_by_id.get(int(room.exam_course_id or 0)) if room else None
        if not room or not course or int(course.batch_id or 0) not in published_batch_ids:
            continue
        output.append({
            "invigilatorId": str(invigilator.id),
            "examRoomId": str(room.id),
            "examCourseId": str(course.id),
            "courseName": course.course_name or "",
            "className": course.class_name or "",
            "examDate": course.exam_date or "",
            "startTime": course.start_time or "",
            "endTime": course.end_time or "",
            "classroom": room.classroom_text or "",
            "role": invigilator.role,
            "confirmStatus": invigilator.confirm_status,
        })
    output.sort(key=lambda row: (row["startTime"], row["examCourseId"], row["examRoomId"]))
    return output


def pending_grade_todos(db, user) -> list[dict]:
    from app.models import UnifiedTodo

    user_id = _resolve_user_id(db, user)
    if not user_id:
        return []
    rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_type == "AA_GRADE_TASK",
        UnifiedTodo.todo_type == _GRADE_TODO,
        UnifiedTodo.assignee_id == int(user_id),
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id)).all()
    return [{
        "todoId": str(row.id),
        "todoType": _GRADE_TODO,
        "gradeTaskId": str(row.source_biz_id or ""),
        "title": row.title or "待录成绩",
        "route": f"{_GRADE_ROUTE}?id={int(row.source_biz_id)}" if row.source_biz_id else _GRADE_ROUTE,
    } for row in rows]


def teacher_work_cues(db, user, *, exam_date: str) -> dict:
    return {
        "invigilations": today_invigilations(db, user, exam_date=exam_date),
        "gradeTodos": pending_grade_todos(db, user),
    }
