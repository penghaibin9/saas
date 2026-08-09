"""考务统一公开入口。

复用既有考务状态机，集中补齐正式学期写保护、名单版本冻结、铺位完整性、发布门禁、
考试结束和归档闭环。本模块不修改其它模块函数对象，也不依赖导入顺序安装规则。

对其它 service 暴露的状态/DTO/审计适配必须从这里走公开名字；调用方不得直接依赖
academic_affairs_exam_service 的下划线私有常量。这样 services 包把公开入口绑定到 facade 后，
学生门户等消费者仍然只依赖稳定契约，不受内部模块拆分/重绑定影响。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.core.affairs_security import _derive_keys, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found

from . import academic_affairs_exam_service as _legacy
from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    require_consumer_snapshot_current,
    resolve_versioned_roster,
)

# ── Public deferred-exam contract ──────────────────────────────────────────
# Consumers outside the legacy exam implementation must use these names rather
# than `_D_*`. Values remain owned by the canonical legacy state machine.
DEFER_STATUS_COUNSELOR_REVIEW = _legacy._D_COUNSELOR
DEFER_STATUS_APPROVED = _legacy._D_APPROVED
DEFER_STATUS_REJECTED = _legacy._D_REJECTED
DEFER_TERMINAL_STATUSES = frozenset({DEFER_STATUS_APPROVED, DEFER_STATUS_REJECTED})


def deferred_exam_dto(row) -> dict:
    """Public DTO adapter for an AaDeferredExam row."""
    return _legacy._defer_dto(row)


def record_exam_audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    """Public audit adapter; keeps the canonical exam audit format in one place."""
    return _legacy._audit(db, biz_type, biz_id, action, detail, before, after)


def _status(value) -> str:
    return str(value or "").strip().upper()


def create_batch(user, body):
    """建考务批次必须绑定正式且仍可写学期。"""
    from app.models import AaExamBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    term_id = getattr(body, "termId", None)
    if not term_id:
        raise AppException("VALIDATION_ERROR", "考务批次必须绑定正式学期termId")
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        guard_term_writable(db, int(term_id))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _legacy._bad("批次名称必填")
        batch = AaExamBatch(
            tenant_id=_legacy._tid(),
            batch_name=name,
            term_id=int(term_id),
            exam_type=getattr(body, "examType", None) or "FINAL",
            exam_week_start=getattr(body, "examWeekStart", None),
            exam_week_end=getattr(body, "examWeekEnd", None),
            college_scope_json=(
                json.dumps(body.collegeScope, ensure_ascii=False)
                if getattr(body, "collegeScope", None) else None
            ),
            status=_legacy._B_DRAFT,
        )
        db.add(batch)
        db.flush()
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_CREATE", f"建考试批次 {name}")
        db.commit()
        return _legacy._batch_dto(batch)


def confirm_course(user, cid, action):
    """学院确认课程时冻结当前正式名单；退回/移除不生成快照。"""
    action = _status(action)
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
                db,
                "EXAM_COURSE",
                int(course.id),
                int(course.teaching_task_id),
                roster=official,
            )
        else:
            course.status = "REMOVED"
        _legacy._audit(
            db,
            "EXAM_COURSE",
            course.id,
            "EXAM_COURSE_CONFIRM",
            f"{action} {course.course_name};rosterVersion={roster_identity['rosterVersionId'] if roster_identity else '-'}",
        )
        db.commit()
        result = _legacy._course_dto(course)
        result["expectedStudents"] = course.expected_students
        result["rosterIdentity"] = roster_identity
        return result


def set_course_schedule(user, cid, body):
    """设置考试时间/时长——批次一旦发布/结束/归档，考试时间就是已通知考生和监考的正式事实，
    禁止普通 UPDATE 悄悄改写；只能在课程尚未确认或课程确认后、发布前的编排阶段调整。"""
    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        course = _legacy._get_course(db, int(cid))
        _legacy._check_college_scope(ctx, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_DRAFT, _legacy._B_CONFIRMED):
            raise AppException(
                "DATA_CONFLICT",
                f"批次已{batch.status}，考试时间已是正式事实，禁止直接修改；如需改期请先走批次退回流程",
                http_status=409,
            )
        if course.status == "REMOVED":
            raise _legacy._invalid("该考试课程已移除，不可设置时间")
        before = f"{course.exam_date} {course.start_time}-{course.end_time}"
        course.exam_date = getattr(body, "examDate", None) or course.exam_date
        course.start_time = getattr(body, "startTime", None) or course.start_time
        course.end_time = getattr(body, "endTime", None) or course.end_time
        course.duration_minutes = getattr(body, "durationMinutes", None) or course.duration_minutes
        after = f"{course.exam_date} {course.start_time}-{course.end_time}"
        _legacy._audit(db, "EXAM_COURSE", course.id, "EXAM_COURSE_SCHEDULE", f"设时间 {after}", before, after)
        db.commit()
        return _legacy._course_dto(course)


def list_courses(user, bid, page=1, page_size=100):
    rows, total = _legacy.list_courses(user, bid, page, page_size)
    with _legacy.session() as db:
        for row in rows:
            row["rosterIdentity"] = get_consumer_snapshot(
                db,
                "EXAM_COURSE",
                int(row["examCourseId"]),
            )
    return rows, total


def _effective_room_capacity(room) -> int:
    capacity = int(getattr(room, "capacity", 0) or 0)
    if _status(getattr(room, "seat_mode", None)) == "SPACED":
        return (capacity + 1) // 2
    return capacity


def assign_seats(user, room_id, student_ids):
    """铺位只允许当前冻结名单成员，同一课程跨考场不可重复。"""
    from app.models import AaExamRoom, AaExamRoomStudent, StudentProfile

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id),
            AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.is_deleted.is_(False),
        ).first()
        if not room:
            raise not_found("考场不存在")
        course = _legacy._get_course(db, room.exam_course_id)
        _legacy._check_college_scope(context, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid("仅课程确认/编排阶段可铺位")
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "考试课程未关联教学任务，无法核验考生名单")

        snapshot, _current = require_consumer_snapshot_current(
            db,
            "EXAM_COURSE",
            int(course.id),
            int(course.teaching_task_id),
        )
        requested = [int(value) for value in student_ids if str(value).isdigit()]
        if len(requested) != len(set(requested)):
            raise AppException("VALIDATION_ERROR", "铺位名单内学生重复")
        frozen_ids = {int(value) for value in snapshot["studentIds"]}
        outside = sorted(set(requested) - frozen_ids)
        if outside:
            raise AppException(
                "VALIDATION_ERROR",
                f"有 {len(outside)} 名学生不在考试课程冻结名单",
                details={"studentIds": [str(value) for value in outside]},
            )

        other_seats = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.exam_course_id == course.id,
            AaExamRoomStudent.exam_room_id != room.id,
            AaExamRoomStudent.student_id.in_(requested or [0]),
            AaExamRoomStudent.is_deleted.is_(False),
        ).all()
        if other_seats:
            raise AppException(
                "DATA_CONFLICT",
                f"有 {len(other_seats)} 名学生已安排在本课程其它考场",
                details={"studentIds": [str(row.student_id) for row in other_seats]},
                http_status=409,
            )

        usable_capacity = _effective_room_capacity(room)
        if len(requested) > usable_capacity:
            raise _legacy._conflict(f"考生数 {len(requested)} 超过考场有效容量 {usable_capacity}")

        profiles = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.id.in_(requested or [0]),
            StudentProfile.is_deleted.is_(False),
        ).all()
        profile_by_id = {int(profile.id): profile for profile in profiles}
        missing_profiles = sorted(set(requested) - set(profile_by_id))
        if missing_profiles:
            raise AppException(
                "DATA_CONFLICT",
                "冻结名单存在已失效学生主档，须先完成名单治理",
                details={"studentIds": [str(value) for value in missing_profiles]},
                http_status=409,
            )
        ordered = sorted(requested, key=lambda value: (profile_by_id[value].student_no or "", value))
        if _status(room.seat_mode) == "RANDOM":
            ordered = sorted(
                requested,
                key=lambda value: hashlib.sha256(f"{room.id}:{value}".encode()).hexdigest(),
            )

        db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.exam_room_id == room.id,
            AaExamRoomStudent.tenant_id == _legacy._tid(),
        ).delete(synchronize_session=False)
        for index, student_id in enumerate(ordered, start=1):
            profile = profile_by_id[student_id]
            seat_no = index * 2 - 1 if _status(room.seat_mode) == "SPACED" else index
            db.add(AaExamRoomStudent(
                tenant_id=_legacy._tid(),
                exam_room_id=room.id,
                exam_course_id=course.id,
                student_id=student_id,
                student_no=profile.student_no,
                student_name=profile.real_name,
                seat_no=seat_no,
                admission_no=f"{course.id}{seat_no:04d}",
                attendance_status="NOT_STARTED",
            ))
        room.planned_count = len(ordered)
        _legacy._audit(
            db,
            "EXAM_ROOM",
            room.id,
            "EXAM_SEAT_ASSIGN",
            f"{room.seat_mode} 铺位 {len(ordered)} 人 rosterVersion={snapshot['rosterVersionId']}",
        )
        db.commit()


def build_seat_plan(user, room_id):
    """排座后返回正式座位映射；同一冻结名单版本决定同一随机排座结果。"""
    from app.models import AaExamRoom, AaExamRoomStudent

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id),
            AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.is_deleted.is_(False),
        ).first()
        if not room:
            raise not_found("考场不存在")
        course = _legacy._get_course(db, room.exam_course_id)
        _legacy._check_college_scope(context, course.college_id)
        snapshot = get_consumer_snapshot(db, "EXAM_COURSE", int(course.id))
        rows = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.exam_room_id == room.id,
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.is_deleted.is_(False),
        ).order_by(AaExamRoomStudent.seat_no.asc(), AaExamRoomStudent.id.asc()).all()
        return {
            "examRoomId": str(room.id),
            "examCourseId": str(course.id),
            "seatMode": room.seat_mode,
            "rosterIdentity": snapshot,
            "items": [
                {
                    "studentId": str(row.student_id),
                    "studentNo": row.student_no,
                    "studentName": row.student_name,
                    "seatNo": row.seat_no,
                    "admissionNo": row.admission_no,
                }
                for row in rows
            ],
        }


def add_room(user, cid, body):
    """手工加考场也必须使用正式容量与考点事实。"""
    from app.models import AaExamRoom

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        course = _legacy._get_course(db, int(cid))
        _legacy._check_college_scope(context, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid("仅课程确认/编排阶段可加考场")
        classroom_text = (getattr(body, "classroom", None) or "").strip()
        if not classroom_text:
            raise AppException("VALIDATION_ERROR", "考场教室必填")
        capacity = int(getattr(body, "capacity", 0) or 0)
        if capacity <= 0:
            raise AppException("VALIDATION_ERROR", "考场容量必须大于0")
        room = AaExamRoom(
            tenant_id=_legacy._tid(),
            exam_course_id=course.id,
            classroom_text=classroom_text,
            classroom_id=_legacy._resolve_classroom_id(db, classroom_text),
            capacity=capacity,
            seat_mode=getattr(body, "seatMode", None) or "NORMAL",
            planned_count=0,
            status="ACTIVE",
        )
        db.add(room)
        db.flush()
        _legacy._audit(db, "EXAM_ROOM", room.id, "EXAM_ROOM_ADD", f"{classroom_text} 容量{capacity}")
        db.commit()
        return _legacy._room_dto(room)


def list_rooms(user, cid):
    return _legacy.list_rooms(user, cid)


def add_invigilator(user, room_id, body):
    from app.models import AaExamInvigilator, AaExamRoom

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id),
            AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.is_deleted.is_(False),
        ).first()
        if not room:
            raise not_found("考场不存在")
        course = _legacy._get_course(db, room.exam_course_id)
        _legacy._check_college_scope(context, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
        