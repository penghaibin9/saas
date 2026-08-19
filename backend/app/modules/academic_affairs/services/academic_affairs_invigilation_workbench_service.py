"""C-W3 teacher invigilation workbench read projection.

This module does not own exam assignments.  It projects the current canonical
AaExamInvigilator row through ACTIVE room -> CONFIRMED course -> PUBLISHED/FINISHED batch.
Published reassignment remains exclusively owned by academic_affairs_exam_facade.change_invigilator;
therefore a reassignment is observed here by the same invigilator row moving to the new teacher.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException, no_permission
from app.services.db_service import _tid, session

_FORMAL_BATCH_STATES = ("PUBLISHED", "FINISHED")


def _teacher_keys(user) -> set[str]:
    return {str(value).strip() for value in _derive_keys(user or {}) if str(value).strip()}


def _require_teacher_identity(user) -> set[str]:
    user = user or {}
    user_type = str(user.get("userType") or "").strip().upper()
    role = str(user.get("currentRoleCode") or "").strip().upper()
    if user_type == "STUDENT" or role == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    keys = _teacher_keys(user)
    if not keys:
        raise no_permission("当前教职工账号缺少稳定工号，请联系管理员")
    return keys


def _as_of_date(db, value: str | None) -> str:
    if value:
        text = str(value).strip()
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "fromDate 必须为 YYYY-MM-DD") from exc
    from .student_exam_read_service import _tenant_timezone

    zone, _zone_name = _tenant_timezone(db)
    return datetime.now(zone).date().isoformat()


def project_my_invigilations(db, user, *, from_date: str | None = None) -> dict:
    """Project this teacher's formal current/future invigilation facts in one read query."""
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    keys = sorted(_require_teacher_identity(user))
    as_of = _as_of_date(db, from_date)
    rows = db.execute(
        select(AaExamInvigilator, AaExamRoom, AaExamCourse, AaExamBatch)
        .join(AaExamRoom, AaExamRoom.id == AaExamInvigilator.exam_room_id)
        .join(AaExamCourse, AaExamCourse.id == AaExamRoom.exam_course_id)
        .join(AaExamBatch, AaExamBatch.id == AaExamCourse.batch_id)
        .where(
            AaExamInvigilator.tenant_id == _tid(),
            AaExamInvigilator.teacher_key.in_(keys),
            AaExamInvigilator.is_deleted.is_(False),
            AaExamRoom.tenant_id == _tid(),
            AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False),
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.status == "CONFIRMED",
            AaExamCourse.exam_date.is_not(None),
            AaExamCourse.exam_date >= as_of,
            AaExamCourse.is_deleted.is_(False),
            AaExamBatch.tenant_id == _tid(),
            AaExamBatch.status.in_(_FORMAL_BATCH_STATES),
            AaExamBatch.published_at.is_not(None),
            AaExamBatch.is_deleted.is_(False),
        )
        .order_by(
            AaExamCourse.exam_date,
            AaExamCourse.start_time,
            AaExamRoom.room_seq,
            AaExamInvigilator.id,
        )
    ).all()

    items = []
    for invigilator, room, course, batch in rows:
        batch_status = str(batch.status or "").upper()
        items.append({
            "invigilatorId": str(invigilator.id),
            "examRoomId": str(room.id),
            "examCourseId": str(course.id),
            "batchId": str(batch.id),
            "batchName": batch.batch_name or "",
            "batchStatus": batch_status,
            "publishedAt": batch.published_at.isoformat() if batch.published_at else None,
            "courseName": course.course_name or "",
            "className": course.class_name or "",
            "examDate": course.exam_date or "",
            "startTime": course.start_time or "",
            "endTime": course.end_time or "",
            "classroom": room.classroom_text or "",
            "roomSeq": int(room.room_seq or 0),
            "teacherKey": invigilator.teacher_key,
            "teacherName": invigilator.teacher_name or "",
            "role": invigilator.role,
            "confirmStatus": invigilator.confirm_status,
            "workStatus": "FINISHED" if batch_status == "FINISHED" else "UPCOMING",
            "source": "AA_EXAM_INVIGILATOR",
        })

    return {
        "scope": "SELF",
        "asOfDate": as_of,
        "items": items,
        "total": len(items),
        "upcomingCount": sum(1 for item in items if item["workStatus"] == "UPCOMING"),
        "finishedCount": sum(1 for item in items if item["workStatus"] == "FINISHED"),
        "note": "只读本人正式监考安排；发布后改派以 canonical AaExamInvigilator 当前归属为准",
    }


def my_invigilation_workbench(user, *, from_date: str | None = None) -> dict:
    with session() as db:
        return project_my_invigilations(db, user, from_date=from_date)
