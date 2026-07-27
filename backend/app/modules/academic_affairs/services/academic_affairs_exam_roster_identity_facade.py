"""R9 考务名单版本最终层。"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_exam_term_facade as _base
from . import academic_affairs_exam_facade as _exam
from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    require_consumer_snapshot_current,
    resolve_versioned_roster,
)

_legacy = _exam._legacy
_original_check_arrangement = _exam._check_arrangement_complete
_original_assign_seats = _exam.assign_seats
_original_list_courses = _exam.list_courses


def __getattr__(name):
    return getattr(_base, name)


def confirm_course(user, cid, action):
    """学院确认考试课程时冻结正式名单；退回移除不生成快照。"""
    action = str(action or "").upper()
    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        course = _legacy._get_course(db, int(cid))
        _legacy._check_college_scope(context, course.college_id)
        if course.status != "PENDING_CONFIRM":
            raise _legacy._invalid("仅待确认课程可操作")
        if action not in {"CONFIRM", "REMOVE", "REJECT"}:
            raise AppException("VALIDATION_ERROR", "考试课程确认动作非法")
        roster_identity = None
        if action == "CONFIRM":
            if not course.teaching_task_id:
                raise AppException("DATA_CONFLICT", "考试课程未关联教学任务，不能确认")
            official = resolve_versioned_roster(db, int(course.teaching_task_id))
            course.expected_students = int(official["memberCount"])
            course.status = "CONFIRMED"
            roster_identity = freeze_consumer_snapshot(
                db, "EXAM_COURSE", int(course.id), int(course.teaching_task_id), roster=official,
            )
        else:
            course.status = "REMOVED"
        _legacy._audit(
            db, "EXAM_COURSE", course.id, "EXAM_COURSE_CONFIRM",
            (
                f"{action} {course.course_name};"
                f"rosterVersion={roster_identity['rosterVersionId'] if roster_identity else '-'}"
            ),
        )
        db.commit()
        result = _legacy._course_dto(course)
        result["expectedStudents"] = course.expected_students
        result["rosterIdentity"] = roster_identity
        return result


def assign_seats(user, room_id, student_ids):
    """铺位前确认考试课程仍引用当前名单版本。名单变更后必须退回重建考试课程。"""
    from app.models import AaExamRoom

    with _legacy.session() as db:
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id),
            AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.is_deleted.is_(False),
        ).first()
        if not room:
            raise _legacy.not_found("考场不存在")
        course = _legacy._get_course(db, int(room.exam_course_id))
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "考试课程未关联教学任务")
        snapshot, _current = require_consumer_snapshot_current(
            db, "EXAM_COURSE", int(course.id), int(course.teaching_task_id),
        )
        requested = {int(value) for value in student_ids if str(value).isdigit()}
        outside = sorted(requested - set(snapshot["studentIds"]))
        if outside:
            raise AppException(
                "VALIDATION_ERROR",
                f"有 {len(outside)} 名学生不在考试课程冻结名单",
                details={"studentIds": [str(value) for value in outside]},
            )
    result = _original_assign_seats(user, room_id, student_ids)
    result["rosterIdentity"] = snapshot
    return result


def _check_arrangement_complete(db, batch_id):
    courses, problems = _original_check_arrangement(db, batch_id)
    for course in courses:
        if not course.teaching_task_id:
            continue
        try:
            snapshot, _current = require_consumer_snapshot_current(
                db, "EXAM_COURSE", int(course.id), int(course.teaching_task_id),
            )
            if int(course.expected_students or 0) != int(snapshot["memberCount"]):
                problems.append(
                    f"{course.course_name or course.id}：预计考生数与冻结名单人数不一致"
                )
        except AppException as exc:
            problems.append(f"{course.course_name or course.id}：{getattr(exc, 'message', None) or str(exc)}")
    return courses, problems


def list_courses(user, bid, page=1, page_size=100):
    rows, total = _original_list_courses(user, bid, page, page_size)
    with _legacy.session() as db:
        for row in rows:
            row["rosterIdentity"] = get_consumer_snapshot(
                db, "EXAM_COURSE", int(row["examCourseId"]),
            )
    return rows, total


# exam facade 内部发布函数引用模块级检查器，因此同时替换内部和公开路径。
_exam._check_arrangement_complete = _check_arrangement_complete
_exam.confirm_course = confirm_course
_exam.assign_seats = assign_seats
_exam.list_courses = list_courses
_legacy.confirm_course = confirm_course
