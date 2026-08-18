"""C15-18 formal teacher-relation guard for classroom attendance.

Attendance facts stay owned by ``academic_affairs_attendance_public_service``. This
adapter closes the legacy single ``AttendanceSession.teacher_key`` authority gap:

- create: formal TeachingClassTeacher + occurrence week decides teacher permission;
- duplicate identity: one formal class/date/slot occurrence, independent of which
  PRIMARY/CO_TEACHER clicked first;
- get/mark/submit: a frozen RosterConsumerSnapshot resolves back to TeachingTask and
  checks the teacher relation for the session's original teaching week;
- legacy sessions with no formal snapshot retain the old stable teacher_key fallback;
- mobile attendance class options are derived from relation-first Teacher Today
  schedule projection, so week-split and co-teachers see the same executable truth.

No Attendance/TeachingClass schema, route registry, or roster state machine is owned here.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import or_, select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_attendance_public_service as public
from . import academic_affairs_teacher_relation_authority as teacher_authority
from . import academic_affairs_teacher_today_service as teacher_today
from . import mobile_academic_affairs_facade as mobile_facade
from .academic_affairs_roster_consumer_service import (
    freeze_consumer_snapshot,
    get_consumer_snapshot,
    resolve_versioned_roster,
)

_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def _relation_scope_in_session(db, attendance_session, user, *, lock: bool = False) -> dict:
    """Authorize one attendance session using its frozen TeachingTask identity."""
    role = public._role(user)
    if role in public._ADMIN_ROLES:
        return {"source": "ADMIN_SCOPE", "authorityWeek": None, "matchedTeacherKeys": []}
    if str(attendance_session.session_type or "").strip().upper() == _ADMIN_SPECIAL:
        raise AppException(
            "NO_DATA_SCOPE",
            "管理员特殊补录场次不属于普通教师授课范围",
            http_status=403,
        )

    snapshot = get_consumer_snapshot(
        db,
        "ATTENDANCE_SESSION",
        int(attendance_session.id),
    )
    if snapshot:
        from app.models import AaTeachingClass

        teaching_class_id = snapshot.get("teachingClassId")
        teaching_class = None
        if teaching_class_id and str(teaching_class_id).isdigit():
            query = db.query(AaTeachingClass).filter(
                AaTeachingClass.id == int(teaching_class_id),
                AaTeachingClass.tenant_id == public._tid(),
                AaTeachingClass.is_deleted.is_(False),
            )
            if lock:
                query = query.with_for_update()
            teaching_class = query.first()
        if not teaching_class:
            raise AppException(
                "DATA_CONFLICT",
                "考勤正式名单快照无法回链教学班，禁止按历史教师字段继续授权",
                details={"sessionId": str(attendance_session.id), "snapshot": snapshot},
                http_status=409,
            )
        week = teacher_authority.teaching_week_for_date(
            db,
            int(teaching_class.term_id),
            attendance_session.session_date,
        )
        if week is None:
            raise AppException(
                "DATA_CONFLICT",
                "考勤日期无法映射到教学周，不能安全裁决教师权限",
                details={
                    "sessionId": str(attendance_session.id),
                    "sessionDate": attendance_session.session_date,
                    "teachingClassId": str(teaching_class.id),
                },
                http_status=409,
            )
        return teacher_authority.require_teacher(
            db,
            SimpleNamespace(id=int(snapshot["teachingTaskId"])),
            user,
            lock=lock,
            week=week,
        )

    # Historical session without a formal roster snapshot: retain the mature stable-key
    # fallback, but never use names/workload/history to infer access.
    key = str(attendance_session.teacher_key or "").strip()
    keys = teacher_authority.user_keys(user)
    if not key:
        raise AppException(
            "NO_DATA_SCOPE",
            "该历史考勤场次缺少稳定教师工号，归属待教务处修复",
            http_status=403,
        )
    if key not in keys:
        raise AppException("NO_DATA_SCOPE", "该考勤场次不在您的授课范围内", http_status=403)
    return {
        "source": "ATTENDANCE_SESSION_LEGACY_FALLBACK",
        "authorityWeek": None,
        "matchedTeacherKeys": [key],
    }


def _guard_no_duplicate_occurrence(db, model, *, class_id: int, session_date: str, slot_no: int, occurrence: dict):
    """Formal occurrence identity must not vary by which co-teacher clicked first."""
    existing = db.query(model).filter(
        model.tenant_id == public._tid(),
        model.class_id == int(class_id or 0),
        model.session_date == str(session_date),
        model.slot_no == int(slot_no),
        model.is_deleted.is_(False),
        or_(model.session_type.is_(None), model.session_type != _ADMIN_SPECIAL),
    ).with_for_update().first()
    if existing:
        raise AppException(
            "DATA_CONFLICT",
            "该正式课次已创建课堂考勤场次，请直接继续点名",
            details={
                "existingSessionId": str(existing.id),
                "teachingTaskId": str(occurrence.get("teachingTaskId") or ""),
                "scheduleItemId": str(occurrence.get("scheduleItemId") or ""),
                "sessionDate": str(session_date),
                "slotNo": int(slot_no),
            },
            http_status=409,
        )


def create_session(user, body) -> dict:
    """Create one formal attendance occurrence under effective-week teacher authority."""
    from app.models import AaAttendanceSession, AaTeachingTask, AaTeachingTaskBatch, AaTerm, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    body = body or {}
    role = public._role(user)
    task_id = body.get("teachingTaskId")
    is_admin_special, special_reason, special_evidence = public._admin_special_contract(
        role,
        body,
        task_id=task_id,
    )
    session_date = str(body.get("sessionDate") or "").strip()
    if not session_date:
        raise AppException("VALIDATION_ERROR", "考勤日期必填")
    slot_no = body.get("slotNo")

    with public.session() as db:
        current_term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == public._tid(),
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).first()
        if not current_term:
            raise AppException("DATA_CONFLICT", "当前学校尚未设置当前学期")
        guard_term_writable(db, current_term.id)

        task = None
        official = None
        occurrence = None
        roster_identity = None
        teacher_scope = {"source": "ADMIN_SCOPE", "authorityWeek": None, "matchedTeacherKeys": []}
        roster_source = _ADMIN_SPECIAL if is_admin_special else "ADMIN_MANUAL"
        if task_id:
            task = db.get(AaTeachingTask, int(task_id))
            if not task or task.is_deleted or task.tenant_id != public._tid():
                raise not_found("教学任务不存在")
            if not public.attendance_task_executable(task.status):
                raise AppException("DATA_CONFLICT", "教学任务须经教师确认并进入可执行状态后才能用于课堂考勤")
            batch = db.get(AaTeachingTaskBatch, int(task.batch_id))
            if not batch or batch.is_deleted or batch.tenant_id != public._tid():
                raise not_found("教学任务批次不存在")
            if int(batch.term_id or 0) != int(current_term.id):
                raise AppException("DATA_CONFLICT", "只能为当前学期教学任务创建考勤")

            requested_class_id = int(body.get("classId") or 0)
            task_class_id = int(task.class_id or 0)
            if requested_class_id and task_class_id and requested_class_id != task_class_id:
                raise AppException("VALIDATION_ERROR", "教学任务与行政班不一致")

            if not is_admin_special:
                occurrence = public.resolve_formal_occurrence(
                    db,
                    task,
                    batch,
                    current_term,
                    session_date=session_date,
                    slot_no=slot_no,
                    expected_schedule_item_id=body.get("scheduleItemId"),
                    lock=True,
                )
                if role not in public._ADMIN_ROLES:
                    teacher_scope = teacher_authority.require_teacher(
                        db,
                        task,
                        user,
                        lock=True,
                        week=int(occurrence["weekNo"]),
                    )

            official = resolve_versioned_roster(db, int(task.id))
            roster_source = _ADMIN_SPECIAL if is_admin_special else official["source"]
            roster = [{
                "studentId": item["studentId"],
                "studentNo": item["studentNo"],
                "realName": item["realName"],
                "status": "PRESENT",
            } for item in official["items"]]
        elif role not in public._ADMIN_ROLES:
            raise AppException("VALIDATION_ERROR", "请选择当前学期本人教学任务后再点名")
        else:
            roster = []

        class_id = int(task.class_id) if task and task.class_id else int(body.get("classId") or 0)
        if task and not class_id:
            class_ids = {
                int(item["classId"])
                for item in official["items"]
                if str(item.get("classId") or "").isdigit()
            }
            class_id = next(iter(class_ids)) if len(class_ids) == 1 else 0
        if not task:
            if not class_id:
                raise AppException("VALIDATION_ERROR", "管理员特殊考勤必须选择明确行政班")
            students = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == public._tid(),
                StudentProfile.class_id == class_id,
                StudentProfile.is_deleted.is_(False),
            )).all()
            roster = [{
                "studentId": str(student.id),
                "studentNo": student.student_no,
                "realName": student.real_name,
                "status": "PRESENT",
            } for student in students]

        if not roster:
            raise not_found("该教学任务暂无可用学生名单")

        if task and role not in public._ADMIN_ROLES and not is_admin_special:
            matched = teacher_scope.get("matchedTeacherKeys") or []
            teacher_key = str(matched[0]) if matched else ""
        elif task:
            teacher_key = str(task.teacher_key or "").strip()
        else:
            teacher_key = str(body.get("teacherKey") or "").strip() or public._primary_teacher_key(user)
        if not teacher_key:
            raise AppException("VALIDATION_ERROR", "无法确定考勤场次教师工号")

        if occurrence:
            _guard_no_duplicate_occurrence(
                db,
                AaAttendanceSession,
                class_id=class_id,
                session_date=occurrence["sessionDate"],
                slot_no=int(occurrence["slotNo"]),
                occurrence=occurrence,
            )

        source_type = _ADMIN_SPECIAL if is_admin_special else "FORMAL_TEACHING"
        occurrence_identity = occurrence["occurrenceIdentity"] if occurrence else None
        source_evidence = (
            special_evidence
            if is_admin_special
            else json.dumps(
                occurrence,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

        item = AaAttendanceSession(
            tenant_id=public._tid(),
            class_id=class_id,
            teaching_task_id=int(task.id) if task else None,
            occurrence_identity=occurrence_identity,
            source_type=source_type,
            source_reason=special_reason if is_admin_special else None,
            source_evidence=source_evidence,
            course_name=(task.course_name if task else str(body.get("courseName") or "").strip() or None),
            term_code=f"{current_term.year_code}-{current_term.term_no}",
            teacher_key=teacher_key,
            session_date=session_date,
            slot_no=int(slot_no) if slot_no else None,
            session_type=(
                _ADMIN_SPECIAL
                if is_admin_special
                else ((str(body.get("sessionType")).strip() or None) if body.get("sessionType") else None)
            ),
            roster_json=json.dumps(roster, ensure_ascii=False),
            total_count=len(roster),
            present_count=len(roster),
            absent_count=0,
            status="DRAFT",
        )
        db.add(item)
        db.flush()
        if task:
            roster_identity = freeze_consumer_snapshot(
                db,
                "ATTENDANCE_SESSION",
                int(item.id),
                int(task.id),
                roster=official,
            )
        audit_detail = (
            f"task={task.id if task else '-'};source={roster_source};course={item.course_name or ''};"
            f"date={session_date};rosterVersion={roster_identity['rosterVersionId'] if roster_identity else '-'};"
            f"teacherAuthority={teacher_scope.get('source')};authorityWeek={teacher_scope.get('authorityWeek')};"
            f"relationIds={','.join(str(value) for value in teacher_scope.get('matchedRelationIds') or [])}"
        )
        if occurrence:
            audit_detail += (
                f";scheduleItem={occurrence['scheduleItemId']}"
                f";activeBatch={occurrence['activeBatchId']}"
                f";scope={occurrence['scopeType']}:{occurrence['scopeId']}"
            )
        if is_admin_special:
            audit_detail += f";reason={special_reason};evidence={special_evidence}"
        public._audit(db, item.id, "CREATE", audit_detail)
        db.commit()
        db.refresh(item)
        result = public._with_source_type(public._row(item))
        result["teachingTaskId"] = str(task.id) if task else None
        result["rosterIdentity"] = roster_identity
        result["occurrenceEvidence"] = occurrence
        result["teacherAuthority"] = teacher_scope
        return result


def get_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession

    with public.session() as db:
        item = db.get(AaAttendanceSession, int(session_id))
        if not item or item.is_deleted or item.tenant_id != public._tid():
            raise not_found("考勤场次不存在")
        teacher_scope = _relation_scope_in_session(db, item, user, lock=False)
        items = json.loads(item.roster_json) if item.roster_json else []
        result = public._with_source_type(public._row(item))
        result["items"] = items
        result["rosterIdentity"] = get_consumer_snapshot(db, "ATTENDANCE_SESSION", int(item.id))
        result["teacherAuthority"] = teacher_scope
        return result


def mark_attendance(session_id, user, body) -> dict:
    from app.models import AaAttendanceSession

    with public.session() as db:
        item = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.id == int(session_id),
            AaAttendanceSession.tenant_id == public._tid(),
            AaAttendanceSession.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("考勤场次不存在")
        _relation_scope_in_session(db, item, user, lock=True)
        if item.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "已提交的考勤不可再修改")

        payload = body or {}
        student_id = str(payload.get("studentId") or "")
        status = str(payload.get("status") or "").upper()
        if status not in public._canonical._STATUS_OK:
            raise AppException("VALIDATION_ERROR", "考勤状态非法")

        roster = json.loads(item.roster_json) if item.roster_json else []
        found = False
        for roster_item in roster:
            if str(roster_item.get("studentId") or "") == student_id:
                roster_item["status"] = status
                found = True
                break
        if not found:
            raise not_found("该生不在本场次名单内")

        item.roster_json = json.dumps(roster, ensure_ascii=False)
        item.present_count = sum(1 for row in roster if row.get("status") == "PRESENT")
        item.absent_count = sum(1 for row in roster if row.get("status") == "ABSENT")
        db.flush()
        db.commit()
        db.refresh(item)
        return {**public._row(item), "items": roster}


def submit_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession

    with public.session() as db:
        item = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.id == int(session_id),
            AaAttendanceSession.tenant_id == public._tid(),
            AaAttendanceSession.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("考勤场次不存在")
        _relation_scope_in_session(db, item, user, lock=True)
        if item.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "该场次已提交")
        item.status = "SUBMITTED"
        public._audit(db, item.id, "SUBMIT", f"present={item.present_count}/{item.total_count}")
        db.commit()
        db.refresh(item)
        row = public._with_source_type(public._row(item))

    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_attendance_warnings
        scan_attendance_warnings(user)
    except Exception:
        logging.getLogger(__name__).exception("attendance submit → scan_attendance_warnings failed")
    return row


def teacher_attendance_class_options(user) -> dict:
    """Mobile class picker from the same relation-first formal schedule projection."""
    schedule = teacher_today.teacher_schedule_projection(user)
    by_task: dict[str, dict] = {}
    patterns_by_task = defaultdict(list)
    for row in schedule.get("items") or []:
        if not row.get("attendanceExecutable"):
            continue
        task_id = str(row.get("teachingTaskId") or "")
        class_id = str(row.get("classId") or "")
        if not task_id or not class_id:
            continue
        patterns_by_task[task_id].append({
            "scheduleItemId": row.get("scheduleItemId"),
            "activeBatchId": row.get("activeBatchId"),
            "scopeType": row.get("scopeType"),
            "scopeId": row.get("scopeId"),
            "weekday": row.get("weekday"),
            "slotNo": row.get("slotNo"),
            "startWeek": row.get("startWeek"),
            "endWeek": row.get("endWeek"),
            "weekParity": row.get("weekParity"),
            "changeId": row.get("changeId"),
            "changeType": row.get("changeType"),
        })
        by_task.setdefault(task_id, {
            "teachingTaskId": task_id,
            "classId": class_id,
            "className": row.get("className") or "",
            "grade": "",
            "courseName": row.get("courseName") or "",
            "teacherKey": row.get("teacherKey") or "",
            "teacherKeys": row.get("teacherKeys") or [],
            "teacherNames": row.get("teacherNames") or [],
            "teacherAuthoritySource": row.get("teacherAuthoritySource") or "",
            "termId": schedule.get("termId") or "",
            "termCode": schedule.get("termCode") or "",
            "taskStatus": row.get("taskStatus") or "",
            "source": "TEACHING_CLASS_TEACHER" if row.get("teacherAuthoritySource") == "TEACHING_CLASS_TEACHER" else "TEACHING_TASK",
            "formalOccurrenceReady": True,
            "formalScheduleStatus": "READY",
            "formalScheduleIssue": "",
        })
    items = []
    for task_id, item in by_task.items():
        item["formalSchedulePatterns"] = patterns_by_task[task_id]
        items.append(item)
    items.sort(key=lambda item: (item["courseName"], item["className"], int(item["teachingTaskId"])))
    return {
        "items": items,
        "hasData": bool(items),
        "termId": schedule.get("termId") or "",
        "termCode": schedule.get("termCode") or "",
        "termStartDate": schedule.get("termStartDate"),
        "termEndDate": schedule.get("termEndDate"),
        "teachingWeeks": schedule.get("teachingWeeks"),
        "note": "仅展示当前学期本人正式教师关系覆盖的可执行课次；周次/CO_TEACHER 与 Teacher Today 同源",
    }


create_session._attendance_teacher_relation_guard = True
get_session._attendance_teacher_relation_guard = True
mark_attendance._attendance_teacher_relation_guard = True
submit_session._attendance_teacher_relation_guard = True
teacher_attendance_class_options._attendance_teacher_relation_guard = True


def install() -> None:
    """Idempotently bind public attendance + mobile picker; no shared registry edits."""
    for name, replacement in (
        ("create_session", create_session),
        ("get_session", get_session),
        ("mark_attendance", mark_attendance),
        ("submit_session", submit_session),
    ):
        original_name = f"_teacher_relation_guard_original_{name}"
        if not hasattr(public, original_name):
            setattr(public, original_name, getattr(public, name))
        setattr(public, name, replacement)
    original_picker = getattr(mobile_facade, "teacher_attendance_class_options")
    if not hasattr(mobile_facade, "_teacher_relation_guard_original_attendance_class_options"):
        mobile_facade._teacher_relation_guard_original_attendance_class_options = original_picker
    mobile_facade.teacher_attendance_class_options = teacher_attendance_class_options
