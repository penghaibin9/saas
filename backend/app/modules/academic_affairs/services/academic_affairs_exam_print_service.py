"""C-W3 Exam formal print projection and issuance audit.

The ordinary room-seat endpoint remains an arrangement workspace read. This module is the
formal-document owner for seating sheets / door signs / admission tickets: only facts that have
already crossed the exam publish boundary may be rendered or issued as official print data.

Historical printing consumes the frozen EXAM_COURSE snapshot plus persisted seat facts. It must
not re-resolve today's TeachingRoster, otherwise a later roster version would rewrite the meaning
of an already-published exam.
"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from .academic_affairs_exam_service import _audit, _check_college_scope, _ctx, _get_batch, _get_course
from .academic_affairs_roster_consumer_service import get_consumer_snapshot

_FORMAL_BATCH_STATES = {"PUBLISHED", "FINISHED", "ARCHIVED"}
_DOCUMENT_KINDS = {"DOOR_LIST", "TICKET"}
_PRINT_ACTION = "EXAM_TICKET_PRINT"


def _conflict(message: str, **details):
    raise AppException("DATA_CONFLICT", message, details=details or None, http_status=409)


def _invalid(message: str, **details):
    raise AppException("VALIDATION_ERROR", message, details=details or None, http_status=422)


def _formal_room_print(db, user, room_id: int, *, lock_room: bool = False) -> dict:
    from app.models import AaExamRoom, AaExamRoomStudent

    context = _ctx(user, db)
    room_query = db.query(AaExamRoom).filter(
        AaExamRoom.id == int(room_id),
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.is_deleted.is_(False),
    )
    if lock_room:
        room_query = room_query.with_for_update()
    room = room_query.first()
    if not room:
        raise not_found("考场不存在")

    course = _get_course(db, int(room.exam_course_id))
    _check_college_scope(context, course.college_id)
    batch = _get_batch(db, int(course.batch_id))

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
        AaExamRoomStudent.tenant_id == _tid(),
        AaExamRoomStudent.exam_room_id == room.id,
        AaExamRoomStudent.is_deleted.is_(False),
    ).order_by(AaExamRoomStudent.seat_no, AaExamRoomStudent.id).all()
    if not seats:
        _conflict("正式考场没有可打印座位数据", examRoomId=str(room.id))

    frozen_ids = [int(value) for value in (snapshot.get("studentIds") or [])]
    if int(snapshot.get("memberCount") or 0) != len(frozen_ids):
        _conflict(
            "考试课程冻结名单计数与成员证据不一致，禁止打印",
            examCourseId=str(course.id),
            frozenCount=len(frozen_ids),
            snapshotMemberCount=int(snapshot.get("memberCount") or 0),
        )

    # A frozen exam-course roster may legitimately be split across several rooms. Therefore the
    # course-wide active seat allocation, not one room's subset, must equal the frozen roster.
    # This also prevents a student from being seated in two active rooms.
    active_rooms = db.query(AaExamRoom).filter(
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.exam_course_id == course.id,
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    ).all()
    active_room_ids = [int(value.id) for value in active_rooms]
    course_seats = db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == _tid(),
        AaExamRoomStudent.exam_room_id.in_(active_room_ids),
        AaExamRoomStudent.is_deleted.is_(False),
    ).all() if active_room_ids else []
    course_seat_ids = [int(value.student_id) for value in course_seats]
    if len(course_seat_ids) != len(set(course_seat_ids)):
        _conflict("正式考试课程存在跨考场重复考生，禁止打印", examCourseId=str(course.id))
    if set(course_seat_ids) != set(frozen_ids):
        _conflict(
            "正式考试课程座位数据与发布时冻结名单不一致，禁止打印",
            examCourseId=str(course.id),
            frozenCount=len(frozen_ids),
            seatedCount=len(course_seat_ids),
        )

    seat_ids = [int(row.student_id) for row in seats]
    if len(seat_ids) != len(set(seat_ids)):
        _conflict("正式座位数据存在重复考生，禁止打印", examRoomId=str(room.id))
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


def formal_room_print(user, room_id: int) -> dict:
    """Read-only official print projection. Merely previewing does not write audit rows."""
    with session() as db:
        return _formal_room_print(db, user, room_id)


def _same_print_scope(detail: str | None, *, print_identity: str, document_kind: str, student_no: str) -> bool:
    try:
        payload = json.loads(detail or "{}")
    except (TypeError, ValueError):
        return False
    return (
        str(payload.get("printIdentity") or "") == print_identity
        and str(payload.get("documentKind") or "") == document_kind
        and str(payload.get("studentNo") or "") == student_no
    )


def record_formal_print(
    user,
    room_id: int,
    *,
    document_kind: str,
    student_no: str | None = None,
    reason: str = "",
) -> dict:
    """Record an append-only issuance/reprint event immediately before browser printing.

    The room row is locked so two concurrent operators cannot both classify the same scope as its
    first print. Reprints require a human reason. The audit payload binds the event to the frozen
    ``printIdentity``; later roster changes therefore cannot make an old issuance look current.
    """
    from app.models import AaExamAuditTrail

    kind = str(document_kind or "").strip().upper()
    if kind not in _DOCUMENT_KINDS:
        _invalid("打印类型仅支持 DOOR_LIST/TICKET", documentKind=kind)
    student_no = str(student_no or "").strip()
    reason = str(reason or "").strip()
    if kind == "DOOR_LIST" and student_no:
        _invalid("门贴/座位表打印不能指定单个学生")

    with session() as db:
        projection = _formal_room_print(db, user, room_id, lock_room=True)
        if kind == "TICKET" and student_no:
            matched = next((row for row in projection["seats"] if str(row.get("studentNo") or "") == student_no), None)
            if not matched:
                raise not_found("该考场不存在指定学生的正式准考证")

        prior_rows = db.query(AaExamAuditTrail.detail).filter(
            AaExamAuditTrail.tenant_id == _tid(),
            AaExamAuditTrail.biz_type == "EXAM_ROOM",
            AaExamAuditTrail.biz_id == int(room_id),
            AaExamAuditTrail.action == _PRINT_ACTION,
        ).order_by(AaExamAuditTrail.id).all()
        prior_count = sum(
            1 for row in prior_rows
            if _same_print_scope(
                row[0] if isinstance(row, tuple) else getattr(row, "detail", None),
                print_identity=projection["printIdentity"],
                document_kind=kind,
                student_no=student_no,
            )
        )
        is_reprint = prior_count > 0
        if is_reprint and len(reason) < 5:
            _invalid("补打必须填写不少于5字的原因", reprint=True, printSequence=prior_count + 1)

        sequence = prior_count + 1
        detail_payload = {
            "documentKind": kind,
            "printIdentity": projection["printIdentity"],
            "studentNo": student_no,
            "printSequence": sequence,
            "reprint": is_reprint,
            "reason": reason,
        }
        _audit(
            db,
            "EXAM_ROOM",
            int(room_id),
            _PRINT_ACTION,
            json.dumps(detail_payload, ensure_ascii=False, separators=(",", ":")),
        )
        db.commit()
        return {
            "auditRecorded": True,
            "action": _PRINT_ACTION,
            "documentKind": kind,
            "printIdentity": projection["printIdentity"],
            "studentNo": student_no or None,
            "printSequence": sequence,
            "reprint": is_reprint,
        }
