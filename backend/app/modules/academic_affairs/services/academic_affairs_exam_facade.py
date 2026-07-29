"""考务统一公开入口。

复用既有考务状态机，集中补齐正式学期写保护、名单版本冻结、铺位完整性、发布门禁、
考试结束和归档闭环。本模块不修改其它模块函数对象，也不依赖导入顺序安装规则。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.core.exceptions import AppException, not_found

from . import academic_affairs_exam_service as _legacy
from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    require_consumer_snapshot_current,
    resolve_versioned_roster,
)


def __getattr__(name):
    return getattr(_legacy, name)


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
        return {
            "examRoomId": str(room.id),
            "seatCount": len(ordered),
            "seatMode": room.seat_mode,
            "rosterIdentity": snapshot,
        }


def _check_arrangement_complete(db, batch_id):
    """发布前校验时间、冻结名单、座位全集、有效容量和逐考场监考。"""
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
        try:
            snapshot, _current = require_consumer_snapshot_current(
                db,
                "EXAM_COURSE",
                int(course.id),
                int(course.teaching_task_id),
            )
        except AppException as exc:
            problems.append(f"{label}：{getattr(exc, 'message', None) or str(exc)}")
            continue
        official_ids = {int(value) for value in snapshot["studentIds"]}
        if not official_ids:
            problems.append(f"{label}：冻结考生名单为空")
        if int(course.expected_students or 0) != int(snapshot["memberCount"]):
            problems.append(f"{label}：预计考生数与冻结名单人数不一致")

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
            problems.append(f"{label}：仍有 {len(missing)} 名冻结考生未铺位")
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


def publish_batch(user, bid):
    """发布前必须通过冻结名单、铺位和监考完整性检查。"""
    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid(f"仅 COURSE_CONFIRMED/ARRANGED 批次可发布，当前 {batch.status}")
        courses, problems = _check_arrangement_complete(db, batch.id)
        if problems:
            raise _legacy._invalid(
                "编排不完整，不可发布：" + "；".join(problems[:5]) + ("…" if len(problems) > 5 else "")
            )
        if not courses:
            raise _legacy._bad("批次无已确认考试课程")
        batch.status = _legacy._B_PUBLISHED
        batch.published_at = datetime.utcnow()
        sent = _legacy._notify_publish(db, batch, courses)
        _legacy._audit(db, "EXAM_BATCH", batch.id, "EXAM_BATCH_PUBLISH", f"发布，推送 {sent} 条考试通知")
        db.commit()
        try:
            from app.services.message_event_outbox_service import process_pending_outbox
            process_pending_outbox(limit=50, worker_id="aa-exam-inline")
        except Exception:  # noqa: BLE001
            pass
        return _legacy._batch_dto(batch)


def _batch_closure_issues(db, batch_id: int) -> dict:
    from app.models import AaDeferredExam, AaExamCourse, AaExamIncident, AaExamRoomStudent

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
