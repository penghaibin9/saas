"""Explicit atomic MARK audit command for classroom attendance.

AA-010 Gold Deep requires every real per-student attendance state transition to retain
one immutable ``AA_ATTENDANCE / MARK`` row.  The first implementation used a global
SQLAlchemy ``before_flush`` listener; that hook did not produce the required final-DB
evidence under the real browser path.  This guard therefore installs an explicit
``mark_attendance`` command on the relation-aware attendance owner.  Authorization,
row locking, roster mutation, counters and MARK evidence all share one transaction.
"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found

from . import academic_affairs_attendance_public_service as public


def mark_attendance(session_id, user, body, *, include_roster=True) -> dict:
    """Relation-authorized per-student mark + before/after audit in one transaction."""
    from app.models import AaAttendanceSession
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    with public.session() as db:
        item = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.id == int(session_id),
            AaAttendanceSession.tenant_id == public._tid(),
            AaAttendanceSession.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("考勤场次不存在")
        relation_guard._relation_scope_in_session(db, item, user, lock=True)
        if item.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "已提交的考勤不可再修改")

        payload = body or {}
        student_id = str(payload.get("studentId") or "")
        status = str(payload.get("status") or "").upper()
        if status not in public._STATUS_OK:
            raise AppException("VALIDATION_ERROR", "考勤状态非法")

        # Never let corrupted historical JSON escape as an unhandled 500.  The
        # relation guard supplies the same Chinese conflict contract to PC and MP.
        roster = relation_guard._load_roster_or_conflict(item.roster_json)
        found = False
        before_status = ""
        for roster_item in roster:
            if str(roster_item.get("studentId") or "") == student_id:
                before_status = str(roster_item.get("status") or "").strip().upper()
                roster_item["status"] = status
                found = True
                break
        if not found:
            raise not_found("该生不在本场次名单内")

        item.roster_json = json.dumps(roster, ensure_ascii=False)
        item.present_count = sum(1 for row in roster if row.get("status") == "PRESENT")
        item.absent_count = sum(1 for row in roster if row.get("status") == "ABSENT")
        if before_status != status:
            public._audit(
                db,
                item.id,
                "MARK",
                f"student={student_id};before={before_status};after={status}",
            )
        db.flush()
        db.commit()
        db.refresh(item)
        result = {
            **public._row(item),
            **relation_guard._roster_summary(roster, item.total_count),
        }
        if include_roster:
            result["items"] = roster
        else:
            result["item"] = next(
                row for row in roster if str(row.get("studentId") or "") == student_id
            )
        return result


mark_attendance._attendance_teacher_relation_guard = True
mark_attendance._aa010_attendance_mark_audit_guard = True


def install() -> None:
    """Install the explicit command once; no global SQLAlchemy event listener remains."""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    if not hasattr(relation_guard, "_aa010_mark_audit_original_mark_attendance"):
        relation_guard._aa010_mark_audit_original_mark_attendance = relation_guard.mark_attendance
    relation_guard.mark_attendance = mark_attendance
