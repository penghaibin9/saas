"""C-W3 Exam formal print projection.

The ordinary room-seat endpoint remains an arrangement workspace read.  This module is the
formal-document owner for seating sheets / door signs / admission tickets: only facts that have
already crossed the exam publish boundary may be rendered as official print data.

Important: historical printing consumes the frozen EXAM_COURSE snapshot plus persisted seat
facts.  It must not re-resolve today's TeachingRoster, otherwise a later roster version would
rewrite the meaning of an already-published exam.
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_exam_service as _legacy
from .academic_affairs_roster_consumer_service import get_consumer_snapshot

_FORMAL_BATCH_STATES = {"PUBLISHED", "FINISHED", "ARCHIVED"}


def _conflict(message: str, **details):
    raise AppException("DATA_CONFLICT", message, details=details or None, http_status=409)


def formal_room_print(user, room_id: int) -> dict:
    """Return an immutable-source print projection for one official exam room.

    This is strictly read-only.  It validates the published batch, confirmed course, active room,
    frozen EXAM_COURSE roster identity and exact persisted seat set before returning printable
    student fields.  Internal student primary keys are deliberately not exposed to the document.
    """
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

        course = _legacy._get_course(db, int(room.exam_course_id))
        _legacy._check_college_scope(context, course.college_id)
        batch = _legacy._get_batch(db, int(course.batch_id))

        if str(batch.status or "").upper() not in _FORMAL_BATCH_STATES:
            _conflict("考试批次尚未发布，禁止生成正式座位表/门贴/准考证", batchStatus=batch.status)
        if not batch.published_at:
            _conflict("考试批次缺少正式发布时间，禁止生成正式打印件", batchId=str(batch.id))
        if str(course.status or "").upper() != "CONFIRMED":
            _conflict("考试课程不是正式确认状态，禁止生成正式打印件", examCourseId=str(course.id))
        if str(room.status or "").upper() != "ACTIVE":
            _conflict("考场已失效，禁止生成正式打印件", examRoomId=str(room.id))

        snapshot = get_consumer_snapshot(db, "EXAM_COURSE", int(course.id))
        if not snapshot:
            _conflict("考试课程缺少冻结名单证据，禁止生成正式打印件", examCourseId=str(course.id))

        seats = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.exam_room_id == room.id,
            AaExamRoomStudent.is_deleted.is_(False),
        ).order_by(AaExamRoomStudent.seat_no, AaExamRoomStudent.id).all()
        if not seats:
            _conflict("正式考场没有可打印座位数据", examRoomId=str(room.id))

        frozen_ids = [int(value) for value in (snapshot.get("studentIds") or [])]
        seat_ids = [int(row.student_id) for row in seats]
        if len(seat_ids) != len(set(seat_ids)):
            _conflict("正式座位数据存在重复考生，禁止打印", examRoomId=str(room.id))
        if set(seat_ids) != set(frozen_ids):
            _conflict(
                "正式座位数据与发布时冻结名单不一致，禁止打印",
                examRoomId=str(room.id),
                frozenCount=len(frozen_ids),
                seatCount=len(seat_ids),
            )
        if int(room.planned_count or 0) != len(seats):
            _conflict(
                "考场计划人数与正式座位数不一致，禁止打印",
                examRoomId=str(room.id),
                plannedCount=int(room.planned_count or 0),
                seatCount=len(seats),
            )

        published_at = batch.published_at.isoformat() if batch.published_at else None
        roster_identity = {
            "rosterVersionId": str(snapshot.get("rosterVersionId") or ""),
            "rosterVersionNo": snapshot.get("rosterVersionNo"),
            "memberCount": int(snapshot.get("memberCount") or 0),
            "rosterHash": str(snapshot.get("rosterHash") or ""),
        }
        print_identity = (
            f"EXAM:{batch.id}:{course.id}:{room.id}:"
            f"{roster_identity['rosterVersionId']}:{roster_identity['rosterHash']}"
        )
        return {
            "documentKind": "EXAM_ROOM_SEATING",
            "documentStatus": "OFFICIAL",
            "printIdentity": print_identity,
            "batchId": str(batch.id),
            "batchName": batch.batch_name or "",
            "batchStatus": batch.status,
            "publishedAt": published_at,
            "examCourseId": str(course.id),
            "courseName": course.course_name or "",
            "examDate": course.exam_date or "",
            "startTime": course.start_time or "",
            "endTime": course.end_time or "",
            "className": course.class_name or "",
            "examRoomId": str(room.id),
            "roomSeq": int(room.room_seq or 0),
            "classroom": room.classroom_text or "",
            "seatCount": len(seats),
            "rosterIdentity": roster_identity,
            "seats": [
                {
                    "seatNo": row.seat_no,
                    "admissionNo": row.admission_no or "",
                    "studentNo": row.student_no or "",
                    "studentName": row.student_name or "",
                }
                for row in seats
            ],
        }
