"""C15-18 SWAP-safe teacher-week authority for existing attendance sessions.

Formal attendance creation already resolves calendar SWAP target dates back to the
original teaching date before choosing a teacher relation.  Existing-session
get/mark/submit and relation-aware ledger reads must use the same logical date; raw
``session_date`` is the actual makeup date and may sit in a different teaching week.

This narrow adapter patches only those read/reauthorization helpers. It owns no
attendance facts, calendar facts, roster snapshots, or teacher relations.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.exceptions import AppException

from . import academic_affairs_attendance_occurrence_consumer as occurrence
from . import academic_affairs_attendance_teacher_relation_guard as execution_guard
from . import academic_affairs_attendance_teacher_relation_read_guard as read_guard
from . import academic_affairs_teacher_relation_authority as teacher_authority
from .academic_affairs_roster_consumer_service import get_consumer_snapshot

_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def _logical_week(db, term, session_date, *, lock: bool = False) -> tuple[int, str, str]:
    requested = occurrence._parse_date(str(session_date or ""))
    logical_date, calendar_source, _event_id = occurrence._calendar_logical_date(
        db,
        term,
        requested,
        lock=lock,
    )
    week, _weekday = occurrence._week_and_weekday(term, logical_date)
    return int(week), logical_date.isoformat(), calendar_source


def _relation_scope_in_session(db, attendance_session, user, *, lock: bool = False) -> dict:
    public = execution_guard.public
    role = public._role(user)
    if role in public._ADMIN_ROLES:
        return {"source": "ADMIN_SCOPE", "authorityWeek": None, "matchedTeacherKeys": []}
    if str(attendance_session.session_type or "").strip().upper() == _ADMIN_SPECIAL:
        raise AppException(
            "NO_DATA_SCOPE",
            "管理员特殊补录场次不属于普通教师授课范围",
            http_status=403,
        )

    snapshot = get_consumer_snapshot(db, "ATTENDANCE_SESSION", int(attendance_session.id))
    if snapshot:
        from app.models import AaTeachingClass, AaTerm

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
        term = db.query(AaTerm).filter(
            AaTerm.id == int(teaching_class.term_id),
            AaTerm.tenant_id == public._tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
        if not term:
            raise AppException("DATA_CONFLICT", "考勤教学班无法回链有效学期", http_status=409)
        week, logical_date, calendar_source = _logical_week(
            db,
            term,
            attendance_session.session_date,
            lock=lock,
        )
        result = teacher_authority.require_teacher(
            db,
            SimpleNamespace(id=int(snapshot["teachingTaskId"])),
            user,
            lock=lock,
            week=week,
        )
        result["logicalDate"] = logical_date
        result["calendarSource"] = calendar_source
        return result

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


_relation_scope_in_session._attendance_swap_teacher_week_guard = True


def _authorize_bucket(db, bucket):
    if not bucket:
        return None
    attendance_session, snapshot, teaching_class, term, _relation = bucket[0]
    if snapshot is None:
        return attendance_session, {
            "teacherAuthoritySource": "ATTENDANCE_SESSION_LEGACY_FALLBACK",
            "authorityWeek": None,
            "teachingTaskId": None,
            "teachingClassId": None,
            "teacherRelationIds": [],
        }
    if teaching_class is None or term is None:
        return None
    week, logical_date, calendar_source = _logical_week(
        db,
        term,
        attendance_session.session_date,
        lock=False,
    )
    matched = []
    for _session, _snapshot, _teaching_class, _term, relation in bucket:
        if relation is not None and teacher_authority.relation_covers_week(relation, week):
            matched.append(relation)
    if not matched:
        return None
    return attendance_session, {
        "teacherAuthoritySource": "TEACHING_CLASS_TEACHER",
        "authorityWeek": week,
        "logicalDate": logical_date,
        "calendarSource": calendar_source,
        "teachingTaskId": str(snapshot.teaching_task_id),
        "teachingClassId": str(teaching_class.id),
        "teacherRelationIds": [str(row.id) for row in matched],
        "teacherRoleTypes": sorted({str(row.role_type or "PRIMARY").upper() for row in matched}),
    }


def _teacher_sessions(db, user, *, class_id=None, term_code=None, session_type=None, submitted_only=False):
    statement = read_guard._teacher_candidate_statement(
        user,
        class_id=class_id,
        term_code=term_code,
        session_type=session_type,
        submitted_only=submitted_only,
    )
    for bucket in read_guard._group_candidate_rows(db, statement):
        authorized = _authorize_bucket(db, bucket)
        if authorized:
            yield authorized


_teacher_sessions._attendance_swap_teacher_week_guard = True


def install() -> None:
    current = getattr(execution_guard, "_relation_scope_in_session", None)
    if not getattr(current, "_attendance_swap_teacher_week_guard", False):
        if not hasattr(execution_guard, "_swap_teacher_week_original_relation_scope"):
            execution_guard._swap_teacher_week_original_relation_scope = current
        execution_guard._relation_scope_in_session = _relation_scope_in_session

    current_sessions = getattr(read_guard, "_teacher_sessions", None)
    if not getattr(current_sessions, "_attendance_swap_teacher_week_guard", False):
        if not hasattr(read_guard, "_swap_teacher_week_original_teacher_sessions"):
            read_guard._swap_teacher_week_original_teacher_sessions = current_sessions
        read_guard._teacher_sessions = _teacher_sessions
