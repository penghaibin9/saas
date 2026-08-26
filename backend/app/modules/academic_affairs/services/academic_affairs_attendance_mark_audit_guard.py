"""AA-010 atomic audit guards for attendance MARK and warning CLOSE.

AA-010 Gold Deep requires every real per-student attendance state transition to retain
one immutable ``AA_ATTENDANCE / MARK`` row.  It also requires the Teacher Mini warning
follow-up to land in the canonical ``AffairsAuditTrail / ACAD_WARNING / CLOSE`` stream.

The attendance command is installed explicitly so authorization, row locking, roster
mutation, counters and MARK evidence share one transaction.  The legacy academic warning
service still owns compatibility callers, so its audit sink is wrapped narrowly: the
existing ``AcademicAuditTrail / WARNING / 关闭预警`` row is preserved and a canonical CLOSE
row is appended to the same DB session before that legacy command commits.
"""
from __future__ import annotations

import json

from app.core.exceptions import AppException, not_found

from . import academic_affairs_attendance_public_service as public


def mark_attendance(session_id, user, body) -> dict:
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

        roster = json.loads(item.roster_json) if item.roster_json else []
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
        return {**public._row(item), "items": roster}


mark_attendance._attendance_teacher_relation_guard = True
mark_attendance._aa010_attendance_mark_audit_guard = True


def _install_legacy_warning_close_audit_bridge() -> None:
    """Keep legacy warning audit while adding canonical CLOSE in the same transaction."""
    from app.services import academic_service as legacy_academic_service
    from . import academic_affairs_warning_service as warning_service

    current = legacy_academic_service._audit
    if getattr(current, "_aa010_warning_close_audit_bridge", False):
        return

    if not hasattr(legacy_academic_service, "_aa010_warning_close_original_audit"):
        legacy_academic_service._aa010_warning_close_original_audit = current
    original = legacy_academic_service._aa010_warning_close_original_audit

    def _audit_with_canonical_warning_close(
        db, biz_type, biz_id, action, detail="", before="", after=""
    ) -> None:
        original(db, biz_type, biz_id, action, detail, before, after)
        if str(biz_type or "").upper() == "WARNING" and str(action or "") == "关闭预警":
            warning_service._audit(
                db,
                "ACAD_WARNING",
                int(biz_id) if str(biz_id).isdigit() else biz_id,
                "CLOSE",
                detail,
                before,
                after,
            )

    _audit_with_canonical_warning_close._aa010_warning_close_audit_bridge = True
    legacy_academic_service._audit = _audit_with_canonical_warning_close


def install() -> None:
    """Install the explicit MARK command and legacy→canonical warning CLOSE audit bridge."""
    from . import academic_affairs_attendance_teacher_relation_guard as relation_guard

    if not hasattr(relation_guard, "_aa010_mark_audit_original_mark_attendance"):
        relation_guard._aa010_mark_audit_original_mark_attendance = relation_guard.mark_attendance
    relation_guard.mark_attendance = mark_attendance
    _install_legacy_warning_close_audit_bridge()
