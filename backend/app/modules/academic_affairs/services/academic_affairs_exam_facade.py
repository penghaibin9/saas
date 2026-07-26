"""考务服务兼容入口。

不重写排考、发布、监考和缓考状态机，只补生产门禁：
- 人工铺位只能从教学任务官方名单选择；
- 发布前逐课程校验“官方名单=全部考场座位并集”，且每个考场有监考；
- 考试结束前完成到考状态、缓考和异常闭环；
- 归档再次执行同一检查，禁止绕过。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_exam_service as _legacy
from .academic_affairs_teaching_roster_service import resolve_teaching_task_roster


def __getattr__(name):
    return getattr(_legacy, name)


def _status(value) -> str:
    return str(value or "").strip().upper()


def _effective_room_capacity(room) -> int:
    capacity = int(getattr(room, "capacity", 0) or 0)
    if _status(getattr(room, "seat_mode", None)) == "SPACED":
        return (capacity + 1) // 2
    return capacity


def assign_seats(user, room_id, student_ids):
    """人工铺位必须是官方名单子集，同一课程跨考场不可重复。"""
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
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid("仅课程确认/编排阶段可铺位")
        if not course.teaching_task_id:
            raise AppException("DATA_CONFLICT", "考试课程未关联教学任务，无法核验考生名单")

        official = resolve_teaching_task_roster(db, int(course.teaching_task_id))
        if not official["ready"]:
            raise AppException(
                "DATA_CONFLICT",
                f"考试课程官方名单尚不可用：{official['note']}",
                details=official,
                http_status=409,
            )
        requested = [int(value) for value in student_ids if str(value).isdigit()]
        if len(requested) != len(set(requested)):
            raise AppException("VALIDATION_ERROR", "铺位名单内学生重复")
        official_ids = set(int(value) for value in official["studentIds"])
        outside = sorted(set(requested) - official_ids)
        if outside:
            raise AppException(
                "VALIDATION_ERROR",
                f"有 {len(outside)} 名学生不在教学任务正式名单",
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
        profile_by_id = {int(item["studentId"]): item for item in official["items"]}
        ordered = sorted(requested, key=lambda value: (profile_by_id[value]["studentNo"], value))
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
                student_no=profile["studentNo"],
                student_name=profile["realName"],
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
            f"{room.seat_mode} 铺位 {len(ordered)} 人 roster={official['source']}",
        )
        db.commit()
        return {
            "examRoomId": str(room.id),
            "seatCount": len(ordered),
            "seatMode": room.seat_mode,
            "rosterSource": official["source"],
        }


def _check_arrangement_complete(db, batch_id):
    """发布前校验每门课程的时间、官方名单、座位全集与逐考场监考。"""
    from app.models import AaExamCourse, AaExamInvigilator, AaExamRoom, AaExamRoomStudent

    courses = db.query(AaExamCourse).filter(
        AaExamCourse.batch_id == int(batch_id),
        AaExamCourse.tenant_id == _legacy._tid(),
        AaExamCourse.status == "CONFIRMED",
        AaExamCourse.is_deleted.is_(False),
    ).all()
    problems = []
    for course in courses:
        label = course.course_name or f"课程{course.id}"
        if not course.exam_date or not course.start_time or not course.end_time:
            problems.append(f"{label}：考试日期/时间不完整")
        if not course.teaching_task_id:
            problems.append(f"{label}：未关联教学任务")
            continue
        official = resolve_teaching_task_roster(db, int(course.teaching_task_id))
        if not official["ready"]:
            problems.append(f"{label}：{official['note']}")
            continue
        official_ids = set(int(value) for value in official["studentIds"])
        if not official_ids:
            problems.append(f"{label}：正式考生名单为空")

        rooms = db.query(AaExamRoom).filter(
            AaExamRoom.exam_course_id == course.id,
            AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False),
        ).all()
        if not rooms:
            problems.append(f"{label}：无考场")
            continue
        room_ids = [int(room.id) for room in rooms]
        seats = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.exam_room_id.in_(room_ids),
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.is_deleted.is_(False),
        ).all()
        seat_ids = [int(seat.student_id) for seat in seats]
        duplicate_count = len(seat_ids) - len(set(seat_ids))
        missing = official_ids - set(seat_ids)
        extra = set(seat_ids) - official_ids
        if duplicate_count:
            problems.append(f"{label}：跨考场重复安排 {duplicate_count} 人")
        if missing:
            problems.append(f"{label}：仍有 {len(missing)} 名正式考生未铺位")
        if extra:
            problems.append(f"{label}：有 {len(extra)} 名名单外考生")

        seats_by_room = {}
        for seat in seats:
            seats_by_room.setdefault(int(seat.exam_room_id), []).append(seat)
        for room in rooms:
            room_seats = seats_by_room.get(int(room.id), [])
            if not room_seats:
                problems.append(f"{label}：考场{room.room_seq}无座位")
            if len(room_seats) > _effective_room_capacity(room):
                problems.append(f"{label}：考场{room.room_seq}超过有效容量")
            if int(room.planned_count or 0) != len(room_seats):
                problems.append(f"{label}：考场{room.room_seq}计划人数与座位数不一致")
            invigilator_count = db.query(AaExamInvigilator).filter(
                AaExamInvigilator.exam_room_id == room.id,
                AaExamInvigilator.tenant_id == _legacy._tid(),
                AaExamInvigilator.is_deleted.is_(False),
            ).count()
            if not invigilator_count:
                problems.append(f"{label}：考场{room.room_seq}无监考")
    return courses, problems


def _batch_closure_issues(db, batch_id: int) -> dict:
    from app.models import (
        AaDeferredExam,
        AaExamCourse,
        AaExamIncident,
        AaExamRoomStudent,
    )

    courses = db.query(AaExamCourse).filter(
        AaExamCourse.tenant_id == _legacy._tid(),
        AaExamCourse.batch_id == int(batch_id),
        AaExamCourse.status != "REMOVED",
        AaExamCourse.is_deleted.is_(False),
    ).all()
    course_ids = [int(course.id) for course in courses]
    pending_courses = sum(1 for course in courses if _status(course.status) == "PENDING_CONFIRM")
    if not course_ids:
        return {
            "activeCourseCount": 0,
            "pendingCourses": pending_courses,
            "notStartedSeats": 0,
            "activeDefers": 0,
            "unresolvedIncidents": 0,
        }

    not_started = db.query(AaExamRoomStudent).filter(
        AaExamRoomStudent.tenant_id == _legacy._tid(),
        AaExamRoomStudent.exam_course_id.in_(course_ids),
        AaExamRoomStudent.attendance_status == "NOT_STARTED",
        AaExamRoomStudent.is_deleted.is_(False),
    ).count()
    active_defers = db.query(AaDeferredExam).filter(
        AaDeferredExam.tenant_id == _legacy._tid(),
        AaDeferredExam.exam_course_id.in_(course_ids),
        AaDeferredExam.status.notin_(["APPROVED", "REJECTED"]),
        AaDeferredExam.is_deleted.is_(False),
    ).count()
    incidents = db.query(AaExamIncident).filter(
        AaExamIncident.tenant_id == _legacy._tid(),
        AaExamIncident.exam_course_id.in_(course_ids),
        AaExamIncident.status == "ACTIVE",
        AaExamIncident.is_deleted.is_(False),
    ).all()
    unresolved = 0
    for incident in incidents:
        incident_type = _status(incident.incident_type)
        if incident_type == "ABSENT" and bool(incident.risk_alert_sent):
            continue
        if str(incident.discipline_case_ref or "").strip():
            continue
        unresolved += 1
    return {
        "activeCourseCount": len(courses),
        "pendingCourses": pending_courses,
        "notStartedSeats": int(not_started or 0),
        "activeDefers": int(active_defers or 0),
        "unresolvedIncidents": unresolved,
    }


def _closure_error(issues: dict) -> AppException | None:
    blockers = []
    if int(issues.get("activeCourseCount") or 0) <= 0:
        blockers.append("没有有效考试课程")
    if issues.get("pendingCourses"):
        blockers.append(f"待确认考试课程 {issues['pendingCourses']} 门")
    if issues.get("notStartedSeats"):
        blockers.append(f"未登记到考状态考生 {issues['notStartedSeats']} 人")
    if issues.get("activeDefers"):
        blockers.append(f"在途缓考申请 {issues['activeDefers']} 条")
    if issues.get("unresolvedIncidents"):
        blockers.append(f"未闭环考场异常 {issues['unresolvedIncidents']} 条")
    if not blockers:
        return None
    return AppException(
        "DATA_CONFLICT",
        "考务尚未收口：" + "；".join(blockers),
        details=issues,
        http_status=409,
    )


def finish_batch(user, bid):
    """PUBLISHED→FINISHED 前执行考生、缓考和异常闭环检查。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status != _legacy._B_PUBLISHED:
            raise _legacy._invalid("仅 PUBLISHED 批次可结束考试")
        issues = _batch_closure_issues(db, batch.id)
        error = _closure_error(issues)
        if error:
            raise error
        batch.status = _legacy._B_FINISHED
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_FINISH", "考试与异常均已收口")
        db.commit()
        return _legacy._batch_dto(batch)


def archive_batch(user, bid):
    """FINISHED→ARCHIVED 前再次校验，防止直接改库或历史漏检后绕过。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status == _legacy._B_ARCHIVED:
            return _legacy._batch_dto(batch)
        if batch.status != _legacy._B_FINISHED:
            raise _legacy._invalid("仅 FINISHED 批次可归档")
        issues = _batch_closure_issues(db, batch.id)
        error = _closure_error(issues)
        if error:
            raise error
        batch.status = _legacy._B_ARCHIVED
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_ARCHIVE", "考务闭环后归档")
        db.commit()
        return _legacy._batch_dto(batch)


def resolve_incident(user, incident_id: int, action: str, reason: str = "", discipline_case_ref: str = "") -> dict:
    """考场异常闭环：HANDOFF移交线索、CLOSE确认缺考联动、VOID作废误登记。"""
    from app.models import AaExamIncident

    action = _status(action)
    reason = str(reason or "").strip()
    case_ref = str(discipline_case_ref or "").strip()
    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        incident = db.query(AaExamIncident).filter(
            AaExamIncident.id == int(incident_id),
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.is_deleted.is_(False),
        ).first()
        if not incident:
            raise not_found("考场异常不存在")
        course = _legacy._get_course(db, int(incident.exam_course_id))
        batch = _legacy._get_batch(db, int(course.batch_id))
        _legacy._ensure_not_archived(batch)
        if not _legacy._is_school(context):
            _legacy._check_college_scope(context, course.college_id)

        if action == "VOID":
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "作废原因必填且不少于5字")
            incident.status = "VOIDED"
            closure = "VOIDED"
        elif action == "HANDOFF":
            if _status(incident.incident_type) == "ABSENT":
                raise AppException("VALIDATION_ERROR", "缺考异常应执行 CLOSE，不使用处分线索移交")
            if len(case_ref) < 3:
                raise AppException("VALIDATION_ERROR", "处分/后续处理线索编号必填")
            incident.discipline_case_ref = case_ref
            closure = "CASE_LINKED"
        elif action == "CLOSE":
            if _status(incident.incident_type) != "ABSENT":
                raise AppException("VALIDATION_ERROR", "违纪/其他异常须先移交处理线索或作废")
            if not incident.risk_alert_sent:
                raise AppException("DATA_CONFLICT", "缺考风险联动尚未成功，不可关闭", http_status=409)
            closure = "RISK_TRANSFERRED"
        else:
            raise AppException("VALIDATION_ERROR", "action仅支持 HANDOFF/CLOSE/VOID")

        _legacy._audit(
            db,
            "EXAM_INCIDENT",
            incident.id,
            f"EXAM_INCIDENT_{action}",
            f"closure={closure};caseRef={case_ref};reason={reason}"[:990],
        )
        db.commit()
        return {
            "incidentId": str(incident.id),
            "status": incident.status,
            "closureStatus": closure,
            "disciplineCaseRef": incident.discipline_case_ref,
            "resolvedAt": datetime.utcnow().isoformat(),
        }


# 原服务内部或完整路径导入仍应消费统一名单、结束和归档实现。
_legacy.assign_seats = assign_seats
_legacy._check_arrangement_complete = _check_arrangement_complete
_legacy.finish_batch = finish_batch
_legacy.archive_batch = archive_batch
