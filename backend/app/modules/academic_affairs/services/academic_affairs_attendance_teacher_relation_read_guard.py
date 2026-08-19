"""C15-18 relation-aware attendance ledger/statistics reads.

Formal attendance sessions freeze a RosterConsumerSnapshot that points back to the
TeachingTask/TeachingClass.  ``AttendanceSession.teacher_key`` is therefore creator
attribution, not the complete read authority.  This adapter makes generic attendance
ledger/statistics agree with Teacher Today and command execution:

- PRIMARY/CO_TEACHER can read the same formal session when their relation covers the
  session's original teaching week;
- week-split teachers only see sessions inside their own relation windows;
- legacy sessions without a formal roster snapshot keep creator-key fallback;
- admin scope keeps direct SQL COUNT + OFFSET/LIMIT;
- teacher scope streams joined candidates and groups one session at a time, so exact
  relation-week pagination/counting does not materialize the tenant's whole ledger;
- statistics stream accessible submitted sessions and retain only per-student aggregates.

No attendance fact, roster snapshot, teacher relation, or warning state is written here.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException

from . import academic_affairs_attendance_public_service as public
from . import academic_affairs_teacher_relation_authority as teacher_authority

_ADMIN_SPECIAL = "ADMIN_SPECIAL"
_MAX_PAGE_SIZE = 200


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _week_from_term(term, session_date) -> int | None:
    start = _as_date(getattr(term, "start_date", None)) if term else None
    target = _as_date(session_date)
    if not start or not target or target < start:
        return None
    week = ((target - start).days // 7) + 1
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    if teaching_weeks > 0 and week > teaching_weeks:
        return None
    return max(1, int(week))


def _base_conditions(model, *, class_id=None, term_code=None, session_type=None, submitted_only=False):
    conditions = [
        model.tenant_id == public._tid(),
        model.is_deleted.is_(False),
        public._stats_session_type_condition(model, session_type),
    ]
    if submitted_only:
        conditions.append(model.status == "SUBMITTED")
    if class_id:
        conditions.append(model.class_id == int(class_id))
    if term_code:
        conditions.append(model.term_code == str(term_code))
    return conditions


def _teacher_candidate_statement(user, *, class_id=None, term_code=None, session_type=None, submitted_only=False):
    from app.models import AaAttendanceSession, AaTeachingClass, AaTeachingClassTeacher, AaTerm
    from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot

    keys = sorted(teacher_authority.user_keys(user))
    if not keys:
        return None
    conditions = _base_conditions(
        AaAttendanceSession,
        class_id=class_id,
        term_code=term_code,
        session_type=session_type,
        submitted_only=submitted_only,
    )
    statement = (
        select(
            AaAttendanceSession,
            AaRosterConsumerSnapshot,
            AaTeachingClass,
            AaTerm,
            AaTeachingClassTeacher,
        )
        .select_from(AaAttendanceSession)
        .outerjoin(
            AaRosterConsumerSnapshot,
            and_(
                AaRosterConsumerSnapshot.tenant_id == AaAttendanceSession.tenant_id,
                AaRosterConsumerSnapshot.consumer_type == "ATTENDANCE_SESSION",
                AaRosterConsumerSnapshot.consumer_id == AaAttendanceSession.id,
                AaRosterConsumerSnapshot.status == "ACTIVE",
                AaRosterConsumerSnapshot.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            AaTeachingClass,
            and_(
                AaTeachingClass.id == AaRosterConsumerSnapshot.teaching_class_id,
                AaTeachingClass.tenant_id == AaAttendanceSession.tenant_id,
                AaTeachingClass.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            AaTerm,
            and_(
                AaTerm.id == AaTeachingClass.term_id,
                AaTerm.tenant_id == AaAttendanceSession.tenant_id,
                AaTerm.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            AaTeachingClassTeacher,
            and_(
                AaTeachingClassTeacher.teaching_class_id == AaTeachingClass.id,
                AaTeachingClassTeacher.tenant_id == AaAttendanceSession.tenant_id,
                AaTeachingClassTeacher.teacher_key.in_(keys),
                AaTeachingClassTeacher.status == "ACTIVE",
                AaTeachingClassTeacher.is_deleted.is_(False),
            ),
        )
        .where(
            *conditions,
            or_(
                and_(
                    AaRosterConsumerSnapshot.id.is_not(None),
                    AaTeachingClassTeacher.id.is_not(None),
                ),
                and_(
                    AaRosterConsumerSnapshot.id.is_(None),
                    AaAttendanceSession.teacher_key.in_(keys),
                ),
            ),
        )
        .order_by(AaAttendanceSession.id.desc(), AaTeachingClassTeacher.id.asc())
        .execution_options(yield_per=500)
    )
    return statement


def _group_candidate_rows(db, statement):
    """Yield one session plus all matching user relations, keeping memory bounded."""
    if statement is None:
        return
    current_id = None
    bucket = []
    for row in db.execute(statement):
        attendance_session = row[0]
        sid = int(attendance_session.id)
        if current_id is None:
            current_id = sid
        if sid != current_id:
            yield bucket
            bucket = []
            current_id = sid
        bucket.append(row)
    if bucket:
        yield bucket


def _authorize_bucket(bucket) -> tuple[object, dict] | None:
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
    week = _week_from_term(term, attendance_session.session_date)
    if week is None:
        return None
    matched = []
    for _session, _snapshot, _teaching_class, _term, relation in bucket:
        if relation is not None and teacher_authority.relation_covers_week(relation, week):
            matched.append(relation)
    if not matched:
        return None
    return attendance_session, {
        "teacherAuthoritySource": "TEACHING_CLASS_TEACHER",
        "authorityWeek": week,
        "teachingTaskId": str(snapshot.teaching_task_id),
        "teachingClassId": str(teaching_class.id),
        "teacherRelationIds": [str(row.id) for row in matched],
        "teacherRoleTypes": sorted({str(row.role_type or "PRIMARY").upper() for row in matched}),
    }


def _teacher_sessions(db, user, *, class_id=None, term_code=None, session_type=None, submitted_only=False):
    statement = _teacher_candidate_statement(
        user,
        class_id=class_id,
        term_code=term_code,
        session_type=session_type,
        submitted_only=submitted_only,
    )
    for bucket in _group_candidate_rows(db, statement):
        authorized = _authorize_bucket(bucket)
        if authorized:
            yield authorized


def _admin_list(db, *, page_no, size, class_id=None, term_code=None, session_type=None):
    from app.models import AaAttendanceSession

    conditions = _base_conditions(
        AaAttendanceSession,
        class_id=class_id,
        term_code=term_code,
        session_type=session_type,
    )
    total = int(
        db.scalar(select(func.count()).select_from(AaAttendanceSession).where(*conditions)) or 0
    )
    rows = db.scalars(
        select(AaAttendanceSession)
        .where(*conditions)
        .order_by(AaAttendanceSession.id.desc())
        .offset((page_no - 1) * size)
        .limit(size)
    ).all()
    return [public._with_source_type(public._row(row)) for row in rows], total


def list_sessions(user, page=1, page_size=20, class_id=None, term_code=None, session_type=None):
    """Exact relation-aware attendance ledger pagination."""
    try:
        page_no = max(1, int(page or 1))
        size = max(1, min(int(page_size or 20), _MAX_PAGE_SIZE))
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "page/pageSize 必须为整数") from exc

    role = public._role(user)
    with public.session() as db:
        if role in public._ADMIN_ROLES:
            return _admin_list(
                db,
                page_no=page_no,
                size=size,
                class_id=class_id,
                term_code=term_code,
                session_type=session_type,
            )

        start = (page_no - 1) * size
        end = start + size
        total = 0
        items = []
        for attendance_session, authority in _teacher_sessions(
            db,
            user,
            class_id=class_id,
            term_code=term_code,
            session_type=session_type,
        ):
            if start <= total < end:
                item = public._with_source_type(public._row(attendance_session))
                item.update(authority)
                items.append(item)
            total += 1
        return items, total


list_sessions._attendance_teacher_relation_read_guard = True


def _aggregate_sessions(session_rows) -> dict:
    aggregate: dict[str, dict] = {}
    session_count = 0
    for attendance_session, _authority in session_rows:
        session_count += 1
        try:
            roster = json.loads(attendance_session.roster_json) if attendance_session.roster_json else []
        except (TypeError, ValueError, json.JSONDecodeError):
            roster = []
        for roster_item in roster:
            student_id = str(roster_item.get("studentId") or "")
            if not student_id:
                continue
            row = aggregate.setdefault(student_id, {
                "studentId": student_id,
                "studentNo": roster_item.get("studentNo") or "",
                "realName": roster_item.get("realName") or "",
                "present": 0,
                "late": 0,
                "absent": 0,
                "leave": 0,
                "sessions": 0,
            })
            status = str(roster_item.get("status") or "PRESENT").upper()
            key = {"PRESENT": "present", "LATE": "late", "ABSENT": "absent", "LEAVE": "leave"}.get(status)
            if key:
                row[key] += 1
                row["sessions"] += 1
    students = []
    for row in aggregate.values():
        row["absentRate"] = round(row["absent"] / row["sessions"], 3) if row["sessions"] else 0.0
        students.append(row)
    students.sort(key=lambda row: (-row["absent"], -row["late"], row["studentNo"]))
    return {"sessionCount": session_count, "students": students}


def attendance_stats(user, class_id=None, term_code=None, session_type=None):
    """Relation-aware submitted attendance aggregate, streaming formal sessions."""
    from app.models import AaAttendanceSession

    role = public._role(user)
    is_special_scope = str(session_type or "").strip().upper() == _ADMIN_SPECIAL
    with public.session() as db:
        if role in public._ADMIN_ROLES:
            conditions = _base_conditions(
                AaAttendanceSession,
                class_id=class_id,
                term_code=term_code,
                session_type=session_type,
                submitted_only=True,
            )
            statement = (
                select(AaAttendanceSession)
                .where(*conditions)
                .order_by(AaAttendanceSession.id)
                .execution_options(yield_per=500)
            )
            result = _aggregate_sessions((row, {}) for row in db.scalars(statement))
        else:
            result = _aggregate_sessions(_teacher_sessions(
                db,
                user,
                class_id=class_id,
                term_code=term_code,
                session_type=session_type,
                submitted_only=True,
            ))
        result.update({
            "sourceScope": _ADMIN_SPECIAL if is_special_scope else "FORMAL_TEACHING",
            "sourceScopeLabel": "管理员特殊补录" if is_special_scope else "正式课堂",
            "teacherAuthorityPolicy": "TEACHING_CLASS_TEACHER_BY_OCCURRENCE_WEEK",
        })
        return result


attendance_stats._attendance_teacher_relation_read_guard = True


def install() -> None:
    for name, replacement in (("list_sessions", list_sessions), ("attendance_stats", attendance_stats)):
        original_name = f"_teacher_relation_read_original_{name}"
        if not hasattr(public, original_name):
            setattr(public, original_name, getattr(public, name))
        setattr(public, name, replacement)
