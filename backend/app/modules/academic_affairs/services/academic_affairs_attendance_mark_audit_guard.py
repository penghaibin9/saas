"""Atomic before/after audit evidence for classroom attendance MARK changes.

AA-010 Gold Deep requires every real per-student attendance correction to retain an
immutable ``AA_ATTENDANCE / MARK`` history row.  The canonical attendance command
already owns locking, authorization, roster mutation, counters and commit.  This guard
does not replace that command; it observes dirty attendance roster JSON in SQLAlchemy's
``before_flush`` hook and appends audit evidence inside the same database transaction.
"""
from __future__ import annotations

import json

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from . import academic_affairs_attendance_public_service as public


def _status_by_student(raw: str | None) -> dict[str, str]:
    try:
        rows = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        student_id = str(row.get("studentId") or "").strip()
        if not student_id:
            continue
        result[student_id] = str(row.get("status") or "").strip().upper()
    return result


def _append_mark_audits(db: Session, _flush_context, _instances) -> None:
    from app.models import AaAttendanceSession

    for item in tuple(db.dirty):
        if not isinstance(item, AaAttendanceSession):
            continue
        state = inspect(item)
        history = state.attrs.roster_json.history
        if not history.has_changes() or not history.deleted or not history.added:
            continue

        before = _status_by_student(history.deleted[0])
        after = _status_by_student(history.added[0])
        for student_id in sorted(before.keys() & after.keys(), key=lambda value: int(value) if value.isdigit() else value):
            before_status = before[student_id]
            after_status = after[student_id]
            if before_status == after_status:
                continue
            public._audit(
                db,
                item.id,
                "MARK",
                f"student={student_id};before={before_status};after={after_status}",
            )


_append_mark_audits._aa010_attendance_mark_audit_guard = True


def install() -> None:
    """Install once on SQLAlchemy Session; audit rows share the business transaction."""
    if not event.contains(Session, "before_flush", _append_mark_audits):
        event.listen(Session, "before_flush", _append_mark_audits)
