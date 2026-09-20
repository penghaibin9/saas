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

from sqlalchemy import or_, select, text

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission

from . import academic_affairs_attendance_public_service as public
from . import academic_affairs_teacher_relation_authority as teacher_authority
from . import academic_affairs_teacher_today_service as teacher_today
from . import mobile_academic_affairs_facade as mobile_facade
from .academic_affairs_roster_consumer_service import get_consumer_snapshot

_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def _attendance_page_args(page, page_size, *, default_page_size=30) -> tuple[int, int]:
    """Validate a mobile roster page before it reaches the JSON snapshot query."""
    if isinstance(page, bool) or isinstance(page_size, bool):
        raise AppException("VALIDATION_ERROR", "考勤名单页码格式不正确")
    try:
        page_no = int(page)
        size = int(page_size)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "考勤名单页码格式不正确") from exc
    if page_no < 1 or page_no > 100000 or size < 1 or size > 50:
        raise AppException("VALIDATION_ERROR", "考勤名单每页最多50人")
    return page_no, size or default_page_size


def _roster_status(value) -> str:
    status = str(value or "").strip().upper()
    return status if status in public._STATUS_OK else "UNMARKED"


def _roster_summary(rows, stored_total) -> dict:
    """Summarize a roster without trusting its stored aggregate counters.

    The snapshot is historical JSON.  The summary is therefore always derived from
    the canonical roster data, and its integrity state is carried to the client so
    a damaged row cannot be submitted as if the current screen were the full class.
    """
    counts = {"PRESENT": 0, "LATE": 0, "ABSENT": 0, "LEAVE": 0, "UNMARKED": 0}
    student_ids = []
    invalid_row = False
    for row in rows or []:
        if not isinstance(row, dict):
            invalid_row = True
            counts["UNMARKED"] += 1
            continue
        student_id = str(row.get("studentId") or "").strip()
        if not student_id:
            invalid_row = True
        else:
            student_ids.append(student_id)
        counts[_roster_status(row.get("status"))] += 1
    total = len(rows or [])
    try:
        expected = int(stored_total or 0)
    except (TypeError, ValueError):
        expected = -1
    if total != expected:
        integrity = "COUNT_MISMATCH"
    elif not total:
        integrity = "EMPTY"
    elif invalid_row or len(set(student_ids)) != total:
        integrity = "INVALID"
    else:
        integrity = "READY"
    marked = sum(counts[key] for key in public._STATUS_OK)
    return {
        "summary": counts,
        "markedCount": marked,
        "unmarkedCount": counts["UNMARKED"],
        "rosterIntegrity": integrity,
        "total": total,
    }


def _load_roster_or_conflict(raw_roster) -> list[dict]:
    try:
        roster = json.loads(raw_roster) if raw_roster else []
    except (TypeError, ValueError) as exc:
        raise AppException("DATA_CONFLICT", "考勤名单无法读取，请联系教务处核对后再操作", http_status=409) from exc
    if not isinstance(roster, list):
        raise AppException("DATA_CONFLICT", "考勤名单格式异常，请联系教务处核对后再操作", http_status=409)
    return roster


def _roster_page(db, attendance_session, page, page_size) -> dict:
    """Read one roster page in MySQL instead of transporting the whole JSON snapshot."""
    page_no, size = _attendance_page_args(page, page_size)
    params = {
        "tenant_id": public._tid(),
        "session_id": int(attendance_session.id),
    }
    valid = db.execute(text("""
        SELECT COALESCE(JSON_VALID(roster_json), 0) AS roster_valid
        FROM t_aa_attendance_session
        WHERE tenant_id = :tenant_id AND id = :session_id AND is_deleted = 0
    """), params).mappings().first()
    if not valid or not bool(valid["roster_valid"]):
        raise AppException("DATA_CONFLICT", "考勤名单无法读取，请联系教务处核对后再操作", http_status=409)

    rows_sql = """
        SELECT
            roster.roster_position AS roster_position,
            COALESCE(roster.student_id, '') AS student_id,
            COALESCE(roster.student_no, '') AS student_no,
            COALESCE(roster.real_name, '') AS real_name,
            UPPER(COALESCE(NULLIF(roster.attendance_status, ''), 'UNMARKED')) AS attendance_status
        FROM t_aa_attendance_session AS session_row
        JOIN JSON_TABLE(
            IF(COALESCE(JSON_VALID(session_row.roster_json), 0), session_row.roster_json, JSON_ARRAY()),
            '$[*]' COLUMNS (
                roster_position FOR ORDINALITY,
                student_id VARCHAR(64) PATH '$.studentId',
                student_no VARCHAR(100) PATH '$.studentNo',
                real_name VARCHAR(200) PATH '$.realName',
                attendance_status VARCHAR(32) PATH '$.status'
            )
        ) AS roster ON 1 = 1
        WHERE session_row.tenant_id = :tenant_id
          AND session_row.id = :session_id
          AND session_row.is_deleted = 0
    """
    summary = db.execute(text(f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN attendance_status = 'PRESENT' THEN 1 ELSE 0 END), 0) AS present_count,
            COALESCE(SUM(CASE WHEN attendance_status = 'LATE' THEN 1 ELSE 0 END), 0) AS late_count,
            COALESCE(SUM(CASE WHEN attendance_status = 'ABSENT' THEN 1 ELSE 0 END), 0) AS absent_count,
            COALESCE(SUM(CASE WHEN attendance_status = 'LEAVE' THEN 1 ELSE 0 END), 0) AS leave_count,
            COALESCE(SUM(CASE WHEN attendance_status NOT IN ('PRESENT', 'LATE', 'ABSENT', 'LEAVE') THEN 1 ELSE 0 END), 0) AS unmarked_count,
            COALESCE(SUM(CASE WHEN student_id = '' THEN 1 ELSE 0 END), 0) AS blank_student_count,
            COUNT(DISTINCT NULLIF(student_id, '')) AS distinct_student_count
        FROM ({rows_sql}) AS roster_rows
    """), params).mappings().one()
    total = int(summary["total"] or 0)
    stored_total = int(attendance_session.total_count or 0)
    if total != stored_total:
        integrity = "COUNT_MISMATCH"
    elif not total:
        integrity = "EMPTY"
    elif int(summary["blank_student_count"] or 0) or int(summary["distinct_student_count"] or 0) != total:
        integrity = "INVALID"
    else:
        integrity = "READY"

    page_rows = db.execute(text(f"""
        SELECT roster_position, student_id, student_no, real_name, attendance_status
        FROM ({rows_sql}) AS roster_rows
        ORDER BY roster_position ASC
        LIMIT :limit OFFSET :offset
    """), {
        **params,
        "limit": size,
        "offset": (page_no - 1) * size,
    }).mappings().all()
    items = [{
        "studentId": str(row["student_id"] or ""),
        "studentNo": str(row["student_no"] or ""),
        "realName": str(row["real_name"] or ""),
        "status": _roster_status(row["attendance_status"]),
    } for row in page_rows]
    summary_payload = {
        "PRESENT": int(summary["present_count"] or 0),
        "LATE": int(summary["late_count"] or 0),
        "ABSENT": int(summary["absent_count"] or 0),
        "LEAVE": int(summary["leave_count"] or 0),
        "UNMARKED": int(summary["unmarked_count"] or 0),
    }
    marked = sum(summary_payload[key] for key in public._STATUS_OK)
    return {
        "items": items,
        "total": total,
        "page": page_no,
        "pageSize": size,
        "hasMore": page_no * size < total,
        "summary": summary_payload,
        "markedCount": marked,
        "unmarkedCount": summary_payload["UNMARKED"],
        "rosterIntegrity": integrity,
    }


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


def _stable_occurrence_identity(occurrence: dict | None) -> str | None:
    """Derive one stable identity from the frozen formal-schedule facts C already owns."""
    if not occurrence:
        return None
    explicit = str(occurrence.get("occurrenceIdentity") or "").strip()
    if explicit:
        return explicit
    batch_id = str(occurrence.get("activeBatchId") or "").strip()
    item_id = str(occurrence.get("scheduleItemId") or "").strip()
    session_date = str(occurrence.get("sessionDate") or "").strip()
    slot_no = occurrence.get("slotNo")
    if not batch_id or not item_id or not session_date or slot_no in (None, ""):
        raise AppException(
            "DATA_CONFLICT",
            "正式课次缺少稳定来源身份，不能创建考勤",
            details={"occurrence": dict(occurrence)},
            http_status=409,
        )
    return f"{batch_id}:{item_id}:{session_date}:{int(slot_no)}"


def _integrated_provenance_kwargs(
    model,
    *,
    task,
    occurrence_identity,
    source_type,
    source_reason,
    source_evidence,
) -> dict:
    """Persist INT-owned provenance only when the integrated ORM exposes those columns.

    C standalone intentionally owns no attendance provenance migration.  Keeping this
    capability-aware makes the same command safe both before and after the INT schema is
    present, while never dropping the provenance from audit/output evidence.
    """
    values = dict(
        teaching_task_id=int(task.id) if task else None,
        occurrence_identity=occurrence_identity,
        source_type=source_type,
        source_reason=source_reason,
        source_evidence=source_evidence,
    )
    return {name: value for name, value in values.items() if hasattr(model, name)}


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

            official = public.resolve_versioned_roster(db, int(task.id))
            roster_source = _ADMIN_SPECIAL if is_admin_special else official["source"]
            roster = [{
                "studentId": item["studentId"],
                "studentNo": item["studentNo"],
                "realName": item["realName"],
                "status": "UNMARKED",
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
                "status": "UNMARKED",
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
            if not occurrence.get("occurrenceIdentity"):
                occurrence = dict(occurrence)
                occurrence["occurrenceIdentity"] = _stable_occurrence_identity(occurrence)

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
            present_count=0,
            absent_count=0,
            status="DRAFT",
            **_integrated_provenance_kwargs(
                AaAttendanceSession,
                task=task,
                occurrence_identity=occurrence_identity,
                source_type=source_type,
                source_reason=special_reason if is_admin_special else None,
                source_evidence=source_evidence,
            ),
        )
        db.add(item)
        db.flush()
        if task:
            roster_identity = public.freeze_consumer_snapshot(
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
                f";occurrence={occurrence['occurrenceIdentity']}"
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
        result["occurrenceEvidence"] = (
            occurrence
            if occurrence is not None
            else (
                {"sourceType": _ADMIN_SPECIAL, "reason": special_reason, "evidence": special_evidence}
                if is_admin_special
                else None
            )
        )
        result["teacherAuthority"] = teacher_scope
        return result


def get_session(session_id, user, page=None, page_size=None) -> dict:
    from app.models import AaAttendanceSession, SchoolClass

    with public.session() as db:
        item = db.get(AaAttendanceSession, int(session_id))
        if not item or item.is_deleted or item.tenant_id != public._tid():
            raise not_found("考勤场次不存在")
        teacher_scope = _relation_scope_in_session(db, item, user, lock=False)
        result = public._with_source_type(public._row(item))
        school_class = db.get(SchoolClass, int(item.class_id)) if item.class_id else None
        result["className"] = (
            school_class.class_name
            if school_class and not school_class.is_deleted and school_class.tenant_id == public._tid()
            else ""
        )
        # The PC endpoint retains its historical complete-roster contract when it
        # does not request a page.  Mobile callers always pass a bounded page so a
        # large class is not placed in one setData/update payload.
        if page is None:
            items = _load_roster_or_conflict(item.roster_json)
            summary = _roster_summary(items, item.total_count)
            result.update(summary)
            result.update({"items": items, "page": 1, "pageSize": len(items), "hasMore": False})
        else:
            result.update(_roster_page(db, item, page, 30 if page_size is None else page_size))
        result["rosterIdentity"] = get_consumer_snapshot(db, "ATTENDANCE_SESSION", int(item.id))
        result["teacherAuthority"] = teacher_scope
        return result


def mark_attendance(session_id, user, body, *, include_roster=True) -> dict:
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
        if status not in public._STATUS_OK:
            raise AppException("VALIDATION_ERROR", "考勤状态非法")

        roster = _load_roster_or_conflict(item.roster_json)
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
        result = {**public._row(item), **_roster_summary(roster, item.total_count)}
        if include_roster:
            result["items"] = roster
        else:
            result["item"] = next(
                row for row in roster if str(row.get("studentId") or "") == student_id
            )
        return result


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
        try:
            roster = json.loads(item.roster_json) if item.roster_json else []
        except (TypeError, ValueError) as exc:
            raise AppException("DATA_CONFLICT", "考勤名单无法读取，请核对后再提交") from exc
        if not isinstance(roster, list) or not roster or len(roster) != item.total_count:
            raise AppException("DATA_CONFLICT", "考勤名单不完整，请重新核对正式名单")
        student_ids = [str(row.get("studentId") or "") if isinstance(row, dict) else "" for row in roster]
        if not all(student_ids) or len(set(student_ids)) != len(student_ids):
            raise AppException("DATA_CONFLICT", "考勤名单存在缺失或重复学生，不能提交")
        unmarked = sum(
            1 for row in roster
            if not isinstance(row, dict) or row.get("status") not in public._STATUS_OK
        )
        if unmarked:
            raise AppException("DATA_CONFLICT", f"还有 {unmarked} 人未完成点名，不能提交考勤",
                               details={"unmarkedCount": unmarked, "sessionId": str(item.id)})
        item.present_count = sum(1 for row in roster if row["status"] == "PRESENT")
        item.absent_count = sum(1 for row in roster if row["status"] == "ABSENT")
        item.status = "SUBMITTED"
        public._audit(db, item.id, "SUBMIT", f"present={item.present_count}/{item.total_count}")
        db.commit()
        db.refresh(item)
        row = public._with_source_type(public._row(item))

    warning_scan_result = None
    warning_scan_error = None
    try:
        from app.modules.academic_affairs.services.academic_affairs_warning_service import scan_attendance_warnings
        warning_scan_result = scan_attendance_warnings(user)
    except Exception as exc:
        logging.getLogger(__name__).exception("attendance submit → scan_attendance_warnings failed")
        warning_scan_error = str(getattr(exc, "message", None) or exc or "预警扫描未完成")
    return {
        **row,
        "warningScanOk": warning_scan_error is None,
        "warningScanError": None if warning_scan_error is None else "考勤已提交，旷课预警扫描未完成，请由教务处在预警模块重新扫描并核对。",
        "warningScanResult": warning_scan_result,
    }


def teacher_attendance_class_options(user) -> dict:
    """Mobile class picker from the same relation-first formal schedule projection."""
    # This function is installed as the public mobile picker during router registration.
    # Teacher relation narrows data scope but is not a substitute for the canonical
    # permission check: a teacher in another business domain must not enumerate
    # academic classes merely by holding a TEACHER_MINI token.
    enforce_permission(user, "academicAffairs.attendance.view")
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
    """Compatibility hook: explicit public delegates already own command/read routing."""
    original_picker = getattr(mobile_facade, "teacher_attendance_class_options")
    if not hasattr(mobile_facade, "_teacher_relation_guard_original_attendance_class_options"):
        mobile_facade._teacher_relation_guard_original_attendance_class_options = original_picker
    mobile_facade.teacher_attendance_class_options = teacher_attendance_class_options
