"""考务统一公开入口。

复用既有考务状态机，集中补齐正式学期写保护、名单版本冻结、铺位完整性、发布门禁、
考试结束和归档闭环。本模块不修改其它模块函数对象，也不依赖导入顺序安装规则。
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
    """发布前必须通过冻结名单、铺位、监考完整性，以及全校资源冲突门禁。"""
    from . import academic_affairs_exam_conflict_service as conflict_service

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, int(bid))
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid(f"仅 COURSE_CONFIRMED/ARRANGED 批次可发布，当前 {batch.status}")
        # 先取同学期批次行锁，再做检测和写入：两个批次并发抢同一间教室/同一个老师时，
        # 若各自只查不锁，会双双查到"无冲突"再双双发布。锁必须早于检测。
        conflict_service.lock_term_exam_batches(db, batch.term_id)
        db.refresh(batch)
        if batch.status not in (_legacy._B_CONFIRMED, _legacy._B_ARRANGED):
            raise _legacy._invalid(f"批次已被并发操作推进为 {batch.status}，本次发布取消")
        courses, problems = _check_arrangement_complete(db, batch.id)
        if problems:
            raise _legacy._invalid(
                "编排不完整，不可发布：" + "；".join(problems[:5]) + ("…" if len(problems) > 5 else "")
            )
        if not courses:
            raise _legacy._bad("批次无已确认考试课程")
        conflicts = conflict_service.validate_exam_batch_conflicts(db, batch)
        if conflicts["problems"]:
            found = conflicts["problems"]
            raise AppException(
                "DATA_CONFLICT",
                "存在资源冲突，不可发布：" + "；".join(found[:5]) + ("…" if len(found) > 5 else ""),
                details={"conflicts": found[:50], "occupancy": conflicts["occupancy"]},
                http_status=409,
            )
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


def record_incident(user, body):
    """登记缺考/违纪——studentId 不能单凭客户端传入即成为权威：必须先证明该学生在本场
    考试的正式冻结座位名单（AaExamRoomStudent）里，不存在则 409 拒绝，不产生 incident/risk/audit 副作用。"""
    from app.models import AaExamIncident, AaExamRoomStudent, AffairsRiskRecord

    with _legacy.session() as db:
        context = _legacy._ctx(user, db)
        course = _legacy._get_course(db, int(body.examCourseId))
        if not _legacy._is_school(context):
            allowed = getattr(context, "college_ids", None) or set()
            teacher_keys = _derive_keys(user)
            is_college = context.scope_type == "COLLEGE" and course.college_id and int(course.college_id) in allowed
            is_invig = _legacy._is_invigilator_of_course(db, course.id, teacher_keys)
            if not (is_college or is_invig):
                raise no_data_scope("非本人监考场次/本学院，无权登记")
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status not in (_legacy._B_PUBLISHED, _legacy._B_FINISHED):
            raise _legacy._invalid("仅发布/结束后可登记考场异常")

        incident_type = body.incidentType
        student_id = int(body.studentId)
        seat = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.exam_course_id == course.id,
            AaExamRoomStudent.student_id == student_id,
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.is_deleted.is_(False),
        ).first()
        if not seat:
            # 错误码沿用同类判定（merge_deferred「学生不在原考试课程冻结名单」）的 DATA_CONFLICT/409，
            # 不自造 422：本项目冻结契约的业务码表里没有 422 这一档。
            raise AppException(
                "DATA_CONFLICT",
                "该学生不在本场考试的正式冻结座位名单，禁止登记考场异常",
                details={"examCourseId": str(course.id), "studentId": str(student_id)},
                http_status=409,
            )

        exist = db.query(AaExamIncident).filter(
            AaExamIncident.tenant_id == _legacy._tid(),
            AaExamIncident.exam_course_id == course.id,
            AaExamIncident.student_id == student_id,
            AaExamIncident.incident_type == incident_type,
            AaExamIncident.is_deleted.is_(False),
        ).first()
        if exist:
            exist.description = getattr(body, "description", None) or exist.description
            exist.status = "ACTIVE"
            incident = exist
        else:
            incident = AaExamIncident(
                tenant_id=_legacy._tid(), exam_room_id=seat.exam_room_id,
                exam_course_id=course.id, student_id=student_id,
                student_no=seat.student_no, student_name=seat.student_name,
                incident_type=incident_type, description=getattr(body, "description", None),
                recorded_by=_legacy._op(), recorded_at=datetime.utcnow(),
                risk_alert_sent=(incident_type == "ABSENT"), status="ACTIVE",
            )
            db.add(incident)
        seat.attendance_status = "ABSENT" if incident_type == "ABSENT" else "DISCIPLINE_VIOLATION"
        db.flush()

        if incident_type == "ABSENT":
            dup = db.query(AffairsRiskRecord).filter(
                AffairsRiskRecord.tenant_id == _legacy._tid(),
                AffairsRiskRecord.source == "EXAM_ABSENT",
                AffairsRiskRecord.source_ref_id == incident.id,
            ).first()
            if not dup:
                db.add(AffairsRiskRecord(
                    tenant_id=_legacy._tid(), student_id=student_id, source="EXAM_ABSENT",
                    source_ref_id=incident.id, risk_level="MEDIUM",
                    title=f"考试缺考：{course.course_name or '课程'}",
                    detail=f"批次 {batch.batch_name} 课程 {course.course_name} 缺考，需辅导员跟进",
                    status="NEW",
                ))
                incident.risk_alert_sent = True

        _legacy._audit(db, "EXAM_INCIDENT", incident.id, "EXAM_INCIDENT_RECORD",
                       f"{incident_type} 学生{student_id};examRoomStudentId={seat.id}")
        db.commit()
        return {"incidentId": str(incident.id), "incidentType": incident_type, "riskAlertSent": incident.risk_alert_sent}


def defer_apply(user, body):
    """学生申请缓考——examCourseId 不能单凭客户端传入即成为权威：必须先证明本人属于该考试课程
    的正式冻结考生名单（学院确认课程时冻结的 EXAM_COURSE 名单快照，或已铺定的正式座位），
    两者都证明不了就 409 拒绝，不产生进入四级审批链的申请记录。"""
    from app.models import AaDeferredExam, AaExamRoomStudent, StudentProfile

    ctx = get_current_user_ctx() or {}
    with _legacy.session() as db:
        student = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == _legacy._tid(),
            StudentProfile.student_no == ctx.get("studentNo"),
            StudentProfile.is_deleted.is_(False),
        ).first()
        if not student:
            raise not_found("学生档案不存在")
        course = _legacy._get_course(db, int(body.examCourseId))
        if _legacy._exam_started(course):
            raise _legacy._bad("考试已开始，不可申请缓考")

        seat = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _legacy._tid(),
            AaExamRoomStudent.exam_course_id == course.id,
            AaExamRoomStudent.student_id == student.id,
            AaExamRoomStudent.is_deleted.is_(False),
        ).first()
        roster_proof = "SEAT" if seat else ""
        if not seat:
            snapshot = get_consumer_snapshot(db, "EXAM_COURSE", int(course.id))
            frozen_ids = {int(value) for value in (snapshot or {}).get("studentIds") or []}
            if int(student.id) in frozen_ids:
                roster_proof = f"ROSTER:{snapshot['rosterVersionId']}"
        if not roster_proof:
            raise AppException(
                "DATA_CONFLICT",
                "本人不在该考试课程的正式冻结考生名单，无法申请缓考",
                details={"examCourseId": str(course.id)},
                http_status=409,
            )

        active = db.query(AaDeferredExam).filter(
            AaDeferredExam.tenant_id == _legacy._tid(),
            AaDeferredExam.student_id == student.id,
            AaDeferredExam.exam_course_id == course.id,
            AaDeferredExam.status.notin_([_legacy._D_REJECTED, _legacy._D_APPROVED]),
            AaDeferredExam.is_deleted.is_(False),
        ).first()
        if active:
            raise _legacy._conflict("已有进行中的缓考申请")

        deferred = AaDeferredExam(
            tenant_id=_legacy._tid(), student_id=student.id, student_no=student.student_no,
            student_name=student.real_name, exam_course_id=course.id, course_name=course.course_name,
            reason_type=getattr(body, "reasonType", None), reason=getattr(body, "reason", None),
            apply_at=datetime.utcnow(), current_node="COUNSELOR", status=_legacy._D_COUNSELOR,
        )
        db.add(deferred)
        db.flush()
        _legacy._audit(
            db, "DEFERRED_EXAM", deferred.id, "DEFER_APPLY_SUBMIT",
            f"缓考申请 {course.course_name};rosterProof={roster_proof}",
        )
        db.commit()
        return _legacy._defer_dto(deferred)


# ══════════ 教师时间线互斥锁（监考/巡考共用） ══════════

def _lock_teacher_timeline(db, teacher_key: str):
    """取得并锁定该教师的监考/巡考时间线互斥锁。

    冲突检测是"查已有场次 → 比对时段 → 通过则插入"，不是原子操作：两个并发请求都可能
    查到"无冲突"再各自插入，同一个老师就被排进两场同时段的考试。返回前该教师的锁行
    已持有排他锁，调用方须在同一事务内完成"冲突检测→插入/改写"。
    """
    from app.models import AaExamTeacherLock

    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "教师工号不能为空")

    def _query():
        return db.query(AaExamTeacherLock).filter(
            AaExamTeacherLock.tenant_id == _legacy._tid(),
            AaExamTeacherLock.teacher_key == key,
            AaExamTeacherLock.is_deleted.is_(False),
        )

    lock_row = _query().with_for_update().first()
    if lock_row:
        return lock_row
    # 进 savepoint 前先 flush 已有待写数据：begin_nested 之后的 flush 会把 session 里所有
    # pending 对象一起写进这个 savepoint，建锁行撞键回滚时不能连调用方已写的数据一起撤销。
    db.flush()
    try:
        with db.begin_nested():
            lock_row = AaExamTeacherLock(tenant_id=_legacy._tid(), teacher_key=key)
            db.add(lock_row)
            db.flush()
    except IntegrityError:
        lock_row = None
    return _query().with_for_update().first() or lock_row


def _fresh_rows(query):
    """加锁读，返回最新已提交版本。

    MySQL REPEATABLE READ 下，事务里只要在拿锁之前发生过任何普通读（本模块几乎所有函数
    一开始都会 _ctx()/_get_course() 之类），读视图就定格了；此后即使刚拿到教师锁，普通读
    依然看不见并发方刚提交的监考/巡考安排。按方言判断，不用 try/except 兜底：那样会把
    MySQL 的锁等待超时也一并吞掉，守卫恰好在高并发时自动失效。
    """
    try:
        is_mysql = query.session.get_bind().dialect.name == "mysql"
    except Exception:  # noqa: BLE001  取不到方言时保守走普通读
        is_mysql = False
    return query.with_for_update(read=True).all() if is_mysql else query.all()


# ══════════ 考场：canonical classroomId + 并发安全序号分配 ══════════

def add_room(user, cid, body):
    """添加考场——室号在课程行锁下分配，避免并发建考场撞号；优先使用 canonical
    classroomId，不依赖文本模糊匹配（人工建考场用显示名，字典里匹配不上就等于放弃了
    这间教室参与发布门禁的跨批次冲突检测）。"""
    from app.models import AaClassroom, AaExamCourse, AaExamRoom

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        course = _legacy._get_course(db, int(cid))
        _legacy._check_college_scope(ctx, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status != _legacy._B_CONFIRMED:
            raise _legacy._invalid("仅 COURSE_CONFIRMED 阶段可编排考场")

        # 锁课程行：同一门课并发建考场时，室号分配(MAX(room_seq)+1)必须串行，否则两个
        # 并发请求都读到同样的 MAX 再各自 INSERT，只能靠事后撞唯一键补救、体验很差。
        locked_course = db.query(AaExamCourse).filter(
            AaExamCourse.id == course.id, AaExamCourse.tenant_id == _legacy._tid(),
        ).with_for_update().first()
        if not locked_course:
            raise not_found("考试课程不存在")

        classroom_id = getattr(body, "classroomId", None)
        classroom_text = getattr(body, "classroomText", None)
        if classroom_id and str(classroom_id).isdigit():
            room = db.query(AaClassroom).filter(
                AaClassroom.id == int(classroom_id), AaClassroom.tenant_id == _legacy._tid(),
                AaClassroom.is_deleted.is_(False),
            ).first()
            if not room:
                raise not_found("教室不存在")
            if room.status != "AVAILABLE":
                raise AppException("DATA_CONFLICT", "所选教室当前不可用", http_status=409)
            classroom_text = (room.room_name or "").strip() or f"{room.building_name}{room.room_code}"
            classroom_id = int(room.id)
        else:
            classroom_id = _legacy._resolve_classroom_id(db, classroom_text)

        # 课程行锁只保证"同一时刻只有一个事务能算这个课程的下一个室号"，但普通 MAX 查询
        # 仍然可能读到本事务开始时(通常是更早的 _ctx()调用)就已经定格的 REPEATABLE READ
        # 快照——事务B排队等到事务A提交后才拿到锁，此时它的普通读依然看不见A刚插入的行，
        # 于是双方都算出同一个 seq。用加锁读（MySQL FOR UPDATE 聚合查询）强制读最新已提交
        # 数据，同时把已有考场行也纳入本事务的锁范围。
        existing_seqs = db.query(AaExamRoom.room_seq).filter(
            AaExamRoom.exam_course_id == locked_course.id, AaExamRoom.tenant_id == _legacy._tid(),
            AaExamRoom.is_deleted.is_(False),
        ).with_for_update().all()
        seq = (max((int(value) for (value,) in existing_seqs), default=0)) + 1
        row = AaExamRoom(
            tenant_id=_legacy._tid(), exam_course_id=locked_course.id, room_seq=seq,
            classroom_text=classroom_text, classroom_id=int(classroom_id) if classroom_id else None,
            capacity=int(getattr(body, "capacity", 0) or 0),
            seat_mode=getattr(body, "seatMode", None) or "SEQUENTIAL", status="ACTIVE",
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError as exc:
            raise AppException(
                "DATA_CONFLICT", "考场序号并发冲突，请重试", http_status=409,
            ) from exc
        _legacy._audit(db, "EXAM_ROOM", row.id, "EXAM_ROOM_ADD", f"考场{seq} {row.classroom_text}")
        db.commit()
        return _legacy._room_dto(row)


# ══════════ 监考：发布前可指定，发布后只能显式变更 ══════════

def assign_invigilator(user, room_id, teacher_key, teacher_name, role="ASSISTANT"):
    """指定监考——批次一旦发布，监考安排已通知本人，禁止再走这条普通指定入口；
    冲突检测在教师时间线锁下用加锁读，避免并发把同一老师排进两场同时段考试。"""
    from app.models import AaExamInvigilator, AaExamRoom

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id), AaExamRoom.tenant_id == _legacy._tid(),
        ).first()
        if not room:
            raise not_found("考场不存在")
        course = _legacy._get_course(db, room.exam_course_id)
        _legacy._check_college_scope(ctx, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status in (_legacy._B_PUBLISHED, _legacy._B_FINISHED):
            raise AppException(
                "DATA_CONFLICT",
                "批次已发布，监考安排已是正式事实，禁止直接指定；如需换人请走显式变更(change_invigilator)",
                http_status=409,
            )

        key = str(teacher_key or "").strip()
        _lock_teacher_timeline(db, key)
        d0, s0, e0 = course.exam_date, course.start_time, course.end_time
        existing = _fresh_rows(db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.teacher_key == key,
            AaExamInvigilator.is_deleted.is_(False),
        ))
        for inv in existing:
            other_room = db.get(AaExamRoom, int(inv.exam_room_id))
            if not other_room or other_room.id == room.id:
                continue
            other_course = _legacy._get_course(db, other_room.exam_course_id)
            if _legacy._time_overlap(d0, s0, e0, other_course.exam_date,
                                     other_course.start_time, other_course.end_time):
                raise _legacy._conflict(f"教师 {teacher_name or key} 该时段已有监考安排（冲突）")
        dup = db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.exam_room_id == room.id,
            AaExamInvigilator.teacher_key == key, AaExamInvigilator.is_deleted.is_(False),
        ).first()
        if dup:
            raise _legacy._bad("该教师已在本考场监考")
        inv = AaExamInvigilator(
            tenant_id=_legacy._tid(), exam_room_id=room.id, teacher_key=key,
            teacher_name=teacher_name, role=role, confirm_status="ASSIGNED",
        )
        db.add(inv)
        db.flush()
        _legacy._audit(db, "EXAM_INVIGILATOR", inv.id, "EXAM_INVIGILATOR_ADD", f"监考 {teacher_name}")
        db.commit()
        return {"invigilatorId": str(inv.id), "examRoomId": str(room.id), "teacherKey": key, "role": role}


def change_invigilator(user, room_id, old_teacher_key, new_teacher_key, new_teacher_name,
                       reason, new_role=None):
    """发布后调整监考的唯一合法入口：必填原因、冻结前后值、冲突检测走加锁读。

    旧老师和新老师的时间线都要锁——旧老师释放这个时段、新老师占用这个时段是同一个
    事务里的两件事，任何一步失败整体回滚，不留半截换人。
    """
    from app.models import AaExamInvigilator, AaExamRoom

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "调整监考必须填写原因且不少于5字")
    old_key = str(old_teacher_key or "").strip()
    new_key = str(new_teacher_key or "").strip()
    if not old_key or not new_key:
        raise AppException("VALIDATION_ERROR", "原监考教师和新监考教师均为必填")
    if old_key == new_key:
        raise _legacy._bad("新监考教师不能与原监考教师相同")

    with _legacy.session() as db:
        ctx = _legacy._ctx(user, db)
        room = db.query(AaExamRoom).filter(
            AaExamRoom.id == int(room_id), AaExamRoom.tenant_id == _legacy._tid(),
        ).first()
        if not room:
            raise not_found("考场不存在")
        course = _legacy._get_course(db, room.exam_course_id)
        _legacy._check_college_scope(ctx, course.college_id)
        batch = _legacy._get_batch(db, course.batch_id)
        _legacy._ensure_not_archived(batch)

        row = db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.exam_room_id == room.id,
            AaExamInvigilator.teacher_key == old_key, AaExamInvigilator.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("原监考安排不存在")

        _lock_teacher_timeline(db, old_key)
        _lock_teacher_timeline(db, new_key)

        d0, s0, e0 = course.exam_date, course.start_time, course.end_time
        existing = _fresh_rows(db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.teacher_key == new_key,
            AaExamInvigilator.is_deleted.is_(False),
        ))
        for inv in existing:
            other_room = db.get(AaExamRoom, int(inv.exam_room_id))
            if not other_room or other_room.id == room.id:
                continue
            other_course = _legacy._get_course(db, other_room.exam_course_id)
            if _legacy._time_overlap(d0, s0, e0, other_course.exam_date,
                                     other_course.start_time, other_course.end_time):
                raise _legacy._conflict(f"教师 {new_teacher_name or new_key} 该时段已有监考安排（冲突）")
        dup = db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.exam_room_id == room.id,
            AaExamInvigilator.teacher_key == new_key, AaExamInvigilator.is_deleted.is_(False),
        ).first()
        if dup:
            raise _legacy._bad("该教师已在本考场监考")

        before = f"{row.teacher_key}:{row.teacher_name or ''}"
        row.teacher_key = new_key
        row.teacher_name = new_teacher_name
        row.confirm_status = "ASSIGNED"
        if new_role:
            row.role = new_role
        after = f"{row.teacher_key}:{row.teacher_name or ''}"
        _legacy._audit(db, "EXAM_INVIGILATOR", row.id, "EXAM_INVIGILATOR_CHANGE",
                       reason_text[:200], before, after)
        db.commit()
        return {"invigilatorId": str(row.id), "examRoomId": str(room.id),
                "teacherKey": new_key, "role": row.role}


# ══════════ 巡考：发布前可指定，发布后只能显式变更 ══════════

def assign_patrol(user, batch_id, teacher_key, teacher_name, patrol_date, start_time, end_time,
                  area_scope=None):
    """排巡考——批次一旦发布禁止普通指定；冲突检测(巡考互撞/监考互撞)在教师时间线锁下
    用加锁读。"""
    from app.models import AaExamInvigilator, AaExamPatrol, AaExamRoom

    with _legacy.session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _legacy._get_batch(db, batch_id)
        _legacy._ensure_not_archived(batch)
        if batch.status in (_legacy._B_PUBLISHED, _legacy._B_FINISHED):
            raise AppException(
                "DATA_CONFLICT",
                "批次已发布，巡考安排已是正式事实，禁止直接指定；如需换人请走显式变更(change_patrol)",
                http_status=409,
            )

        key = str(teacher_key or "").strip()
        _lock_teacher_timeline(db, key)
        existing = _fresh_rows(db.query(AaExamPatrol).filter(
            AaExamPatrol.tenant_id == _legacy._tid(), AaExamPatrol.teacher_key == key,
            AaExamPatrol.is_deleted.is_(False),
        ))
        for p in existing:
            if _legacy._time_overlap(patrol_date, start_time, end_time,
                                     p.patrol_date, p.start_time, p.end_time):
                raise _legacy._conflict(f"教师 {teacher_name or key} 该时段已有巡考安排（冲突）")
        invs = _fresh_rows(db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.teacher_key == key,
            AaExamInvigilator.is_deleted.is_(False),
        ))
        for inv in invs:
            room = db.get(AaExamRoom, int(inv.exam_room_id))
            if not room:
                continue
            course = _legacy._get_course(db, room.exam_course_id)
            if _legacy._time_overlap(patrol_date, start_time, end_time,
                                     course.exam_date, course.start_time, course.end_time):
                raise _legacy._conflict(f"教师 {teacher_name or key} 该时段有监考任务，不能同时巡考（冲突）")
        row = AaExamPatrol(
            tenant_id=_legacy._tid(), batch_id=batch.id, teacher_key=key, teacher_name=teacher_name,
            patrol_date=patrol_date, start_time=start_time, end_time=end_time,
            area_scope_json=area_scope, status="ASSIGNED",
        )
        db.add(row)
        db.flush()
        _legacy._audit(db, "EXAM_PATROL", row.id, "EXAM_PATROL_ADD", f"巡考 {teacher_name}")
        db.commit()
        return {"patrolId": str(row.id), "batchId": str(batch.id), "teacherKey": key}


def change_patrol(user, patrol_id, new_teacher_key, new_teacher_name, reason,
                  new_patrol_date=None, new_start_time=None, new_end_time=None):
    """发布后调整巡考的唯一合法入口：必填原因、冻结前后值、冲突检测走加锁读。"""
    from app.models import AaExamInvigilator, AaExamPatrol, AaExamRoom

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "调整巡考必须填写原因且不少于5字")
    new_key = str(new_teacher_key or "").strip()
    if not new_key:
        raise AppException("VALIDATION_ERROR", "新巡考教师必填")

    with _legacy.session() as db:
        row = db.query(AaExamPatrol).filter(
            AaExamPatrol.id == int(patrol_id), AaExamPatrol.tenant_id == _legacy._tid(),
            AaExamPatrol.is_deleted.is_(False),
        ).with_for_update().first()
        if not row:
            raise not_found("巡考安排不存在")
        batch = _legacy._get_batch(db, row.batch_id)
        _legacy._require_school(_legacy._ctx(user, db))
        _legacy._ensure_not_archived(batch)

        old_key = row.teacher_key
        patrol_date = new_patrol_date or row.patrol_date
        start_time = new_start_time or row.start_time
        end_time = new_end_time or row.end_time

        if old_key and old_key != new_key:
            _lock_teacher_timeline(db, old_key)
        _lock_teacher_timeline(db, new_key)

        existing = _fresh_rows(db.query(AaExamPatrol).filter(
            AaExamPatrol.tenant_id == _legacy._tid(), AaExamPatrol.teacher_key == new_key,
            AaExamPatrol.id != row.id, AaExamPatrol.is_deleted.is_(False),
        ))
        for p in existing:
            if _legacy._time_overlap(patrol_date, start_time, end_time,
                                     p.patrol_date, p.start_time, p.end_time):
                raise _legacy._conflict(f"教师 {new_teacher_name or new_key} 该时段已有巡考安排（冲突）")
        invs = _fresh_rows(db.query(AaExamInvigilator).filter(
            AaExamInvigilator.tenant_id == _legacy._tid(), AaExamInvigilator.teacher_key == new_key,
            AaExamInvigilator.is_deleted.is_(False),
        ))
        for inv in invs:
            inv_room = db.get(AaExamRoom, int(inv.exam_room_id))
            if not inv_room:
                continue
            inv_course = _legacy._get_course(db, inv_room.exam_course_id)
            if _legacy._time_overlap(patrol_date, start_time, end_time,
                                     inv_course.exam_date, inv_course.start_time, inv_course.end_time):
                raise _legacy._conflict(f"教师 {new_teacher_name or new_key} 该时段有监考任务，不能同时巡考（冲突）")

        before = f"{row.teacher_key}:{row.teacher_name or ''}:{row.patrol_date} {row.start_time}-{row.end_time}"
        row.teacher_key = new_key
        row.teacher_name = new_teacher_name
        row.patrol_date = patrol_date
        row.start_time = start_time
        row.end_time = end_time
        after = f"{row.teacher_key}:{row.teacher_name or ''}:{row.patrol_date} {row.start_time}-{row.end_time}"
        _legacy._audit(db, "EXAM_PATROL", row.id, "EXAM_PATROL_CHANGE", reason_text[:200], before, after)
        db.commit()
        return {"patrolId": str(row.id), "batchId": str(batch.id), "teacherKey": new_key}


# ══════════ 显式静态契约：以下均为无副作用只读或不涉及本轮安全修复的写操作。
# ══════════ 逐个具名重导出，替代原来的 __getattr__ 动态穿透——新增 legacy 函数
# ══════════ 不会自动出现在这里，必须显式登记才能被 Router/其它模块调用到。

add_exam_course = _legacy.add_exam_course
get_batch = _legacy.get_batch
list_batches = _legacy.list_batches
confirm_batch_courses = _legacy.confirm_batch_courses
list_rooms = _legacy.list_rooms
room_seats = _legacy.room_seats
list_invigilators = _legacy.list_invigilators
list_patrols = _legacy.list_patrols
list_incidents = _legacy.list_incidents
defer_list = _legacy.defer_list
defer_resubmit = _legacy.defer_resubmit
defer_review = _legacy.defer_review
list_archived_batches = _legacy.list_archived_batches
batch_stats = _legacy.batch_stats
my_deferrable_courses = _legacy.my_deferrable_courses
my_exam_schedule = _legacy.my_exam_schedule
