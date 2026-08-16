"""C-W2 read-only execution-state projection for Teacher Today.

The module only inspects already-materialized TeachingClass/RosterVersion/Attendance facts.
It must never call an ensure/project/freeze helper and never writes while rendering a teacher
home page.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_, select

from app.services.db_service import _tid

from .academic_affairs_roster_consumer_service import roster_hash

_ADMIN_SPECIAL = "ADMIN_SPECIAL"


def _roster_state(teaching_class, version, member_ids) -> dict:
    if not teaching_class:
        return {
            "rosterReady": False,
            "teachingClassId": None,
            "rosterVersionId": None,
            "rosterVersionNo": None,
            "rosterMemberCount": 0,
            "rosterIssue": "该教学任务尚未形成正式教学班名单",
        }
    class_id = str(teaching_class.id)
    version_id = str(teaching_class.current_roster_version_id or "") or None
    version_no = int(teaching_class.current_roster_version_no or 0) or None
    if str(teaching_class.status or "").upper() != "ACTIVE":
        return {
            "rosterReady": False,
            "teachingClassId": class_id,
            "rosterVersionId": version_id,
            "rosterVersionNo": version_no,
            "rosterMemberCount": 0,
            "rosterIssue": "教学班当前不是 ACTIVE 状态",
        }
    if str(teaching_class.roster_status or "").upper() != "LOCKED" or not version:
        return {
            "rosterReady": False,
            "teachingClassId": class_id,
            "rosterVersionId": version_id,
            "rosterVersionNo": version_no,
            "rosterMemberCount": 0,
            "rosterIssue": "教学班正式名单尚未锁定",
        }
    ids = sorted({int(value) for value in (member_ids or [])})
    expected_count = int(version.member_count or 0)
    if (
        int(version.teaching_class_id or 0) != int(teaching_class.id)
        or str(version.status or "").upper() != "LOCKED"
        or int(version.version_no or 0) != int(teaching_class.current_roster_version_no or 0)
        or expected_count != len(ids)
        or str(version.roster_hash or "") != roster_hash(ids)
    ):
        return {
            "rosterReady": False,
            "teachingClassId": class_id,
            "rosterVersionId": str(version.id),
            "rosterVersionNo": int(version.version_no or 0) or None,
            "rosterMemberCount": len(ids),
            "rosterIssue": "教学班当前名单版本完整性校验失败",
        }
    return {
        "rosterReady": True,
        "teachingClassId": class_id,
        "rosterVersionId": str(version.id),
        "rosterVersionNo": int(version.version_no or 0),
        "rosterMemberCount": len(ids),
        "rosterIssue": "",
    }


def _attendance_state(rows) -> dict:
    values = list(rows or [])
    if not values:
        return {
            "attendanceState": "NOT_STARTED",
            "attendanceSessionId": None,
            "attendanceIssue": "",
        }
    if len(values) > 1:
        return {
            "attendanceState": "CONFLICT",
            "attendanceSessionId": None,
            "attendanceIssue": "同一正式课次存在多个考勤场次，请联系教务处理",
        }
    row = values[0]
    return {
        "attendanceState": str(row.status or "DRAFT").upper(),
        "attendanceSessionId": str(row.id),
        "attendanceIssue": "",
    }


def _action_state(row: dict, roster_state: dict, attendance_state: dict) -> dict:
    """Turn read facts into a safe Teacher Today action without granting write authority."""
    if attendance_state.get("attendanceState") == "CONFLICT":
        return {
            "attendanceAction": "CONFLICT",
            "attendanceActionLabel": "考勤数据冲突",
            "attendanceRoute": None,
            "attendanceBlockReason": attendance_state.get("attendanceIssue") or "同一正式课次存在多个考勤场次",
        }
    if attendance_state.get("attendanceSessionId"):
        status = str(attendance_state.get("attendanceState") or "").upper()
        return {
            "attendanceAction": "OPEN_EXISTING",
            "attendanceActionLabel": "继续点名" if status == "DRAFT" else "查看考勤",
            # C-W2 next slice will replace this temporary block with an exact sessionId deep-link.
            "attendanceRoute": None,
            "attendanceBlockReason": "该课次已有考勤场次，请从课堂考勤列表继续处理",
        }
    if not roster_state.get("rosterReady"):
        return {
            "attendanceAction": "BLOCKED_ROSTER",
            "attendanceActionLabel": "名单未就绪",
            "attendanceRoute": None,
            "attendanceBlockReason": roster_state.get("rosterIssue") or "正式教学名单尚未就绪",
        }
    if not row.get("attendanceExecutable"):
        return {
            "attendanceAction": "BLOCKED_TASK",
            "attendanceActionLabel": "待任务确认",
            "attendanceRoute": None,
            "attendanceBlockReason": row.get("attendanceBlockReason") or "教学任务尚未进入可点名状态",
        }
    return {
        "attendanceAction": "CREATE",
        "attendanceActionLabel": "去点名",
        "attendanceRoute": row.get("attendanceRoute"),
        "attendanceBlockReason": "",
    }


def enrich_today_execution_state(db, items: list[dict]) -> list[dict]:
    """Batch-enrich current Teacher Today rows without materializing missing facts."""
    from app.models import (
        AaAttendanceSession,
        AaTeachingClass,
        AaTeachingClassMember,
        AaTeachingClassRosterVersion,
    )

    rows = [dict(item) for item in (items or [])]
    if not rows:
        return []

    task_ids = sorted({int(row["teachingTaskId"]) for row in rows if str(row.get("teachingTaskId") or "").isdigit()})
    teaching_classes = db.scalars(select(AaTeachingClass).where(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id.in_(task_ids or [0]),
        AaTeachingClass.is_deleted.is_(False),
    )).all()
    classes_by_task = defaultdict(list)
    for row in teaching_classes:
        classes_by_task[int(row.teaching_task_id)].append(row)

    current_version_ids = sorted({
        int(row.current_roster_version_id)
        for row in teaching_classes
        if row.current_roster_version_id
    })
    versions = []
    if current_version_ids:
        versions = db.scalars(select(AaTeachingClassRosterVersion).where(
            AaTeachingClassRosterVersion.tenant_id == _tid(),
            AaTeachingClassRosterVersion.id.in_(current_version_ids),
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        )).all()
    version_by_id = {int(row.id): row for row in versions}

    members = []
    if current_version_ids:
        members = db.scalars(select(AaTeachingClassMember).where(
            AaTeachingClassMember.tenant_id == _tid(),
            AaTeachingClassMember.roster_version_id.in_(current_version_ids),
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        )).all()
    member_ids_by_version = defaultdict(list)
    for member in members:
        member_ids_by_version[int(member.roster_version_id)].append(int(member.student_id))

    class_ids = sorted({int(row.get("classId") or 0) for row in rows if int(row.get("classId") or 0) > 0})
    teacher_keys = sorted({str(row.get("teacherKey") or "") for row in rows if str(row.get("teacherKey") or "")})
    dates = sorted({str(row.get("sessionDate") or "") for row in rows if str(row.get("sessionDate") or "")})
    slots = sorted({int(row.get("slotNo") or 0) for row in rows if int(row.get("slotNo") or 0) > 0})
    attendance_rows = []
    if class_ids and teacher_keys and dates and slots:
        attendance_rows = db.scalars(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.class_id.in_(class_ids),
            AaAttendanceSession.teacher_key.in_(teacher_keys),
            AaAttendanceSession.session_date.in_(dates),
            AaAttendanceSession.slot_no.in_(slots),
            AaAttendanceSession.is_deleted.is_(False),
            or_(
                AaAttendanceSession.session_type.is_(None),
                AaAttendanceSession.session_type != _ADMIN_SPECIAL,
            ),
        )).all()
    sessions_by_key = defaultdict(list)
    for session_row in attendance_rows:
        key = (
            int(session_row.class_id or 0),
            str(session_row.teacher_key or ""),
            str(session_row.session_date or ""),
            int(session_row.slot_no or 0),
        )
        sessions_by_key[key].append(session_row)

    output = []
    for row in rows:
        task_id = int(row.get("teachingTaskId") or 0)
        candidates = classes_by_task.get(task_id, [])
        if len(candidates) > 1:
            roster_state = {
                "rosterReady": False,
                "teachingClassId": None,
                "rosterVersionId": None,
                "rosterVersionNo": None,
                "rosterMemberCount": 0,
                "rosterIssue": "同一教学任务存在多个有效教学班投影，数据冲突",
            }
        else:
            teaching_class = candidates[0] if candidates else None
            version = (
                version_by_id.get(int(teaching_class.current_roster_version_id))
                if teaching_class and teaching_class.current_roster_version_id else None
            )
            member_ids = (
                member_ids_by_version.get(int(version.id), []) if version else []
            )
            roster_state = _roster_state(teaching_class, version, member_ids)

        attendance_key = (
            int(row.get("classId") or 0),
            str(row.get("teacherKey") or ""),
            str(row.get("sessionDate") or ""),
            int(row.get("slotNo") or 0),
        )
        attendance_state = _attendance_state(sessions_by_key.get(attendance_key, []))
        action_state = _action_state(row, roster_state, attendance_state)
        output.append({**row, **roster_state, **attendance_state, **action_state})
    return output
