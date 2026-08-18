"""C-W4 GradeTask deadline / extension authority.

Deadline is a persisted GradeTask fact. It is never inferred from term.end_date.
All mutations lock the grade task, reuse canonical grade data scope, and append an
audit row. Overdue is a read-time derivative; the canonical grade state machine
remains unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.core.exceptions import AppException

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_execution_service as _grade_exec
from . import academic_affairs_grade_service as _grade

_FINAL_STATES = {"PUBLISHED", "ARCHIVED"}
_SUBMITTED_STATES = {"SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "PUBLISHED", "ARCHIVED"}


def _now() -> datetime:
    return datetime.utcnow()


def _parse_deadline(raw) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    else:
        text_value = str(raw or "").strip()
        if not text_value:
            raise AppException("VALIDATION_ERROR", "截止时间必填")
        try:
            value = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "截止时间格式不合法，请提交 ISO-8601 时间") from exc
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=0)


def _deadline_row(db, task_id: int, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    return db.execute(
        text(
            "SELECT deadline_at, deadline_updated_at "
            "FROM t_aa_grade_task "
            "WHERE id=:task_id AND tenant_id=:tenant_id AND is_deleted=0" + suffix
        ),
        {"task_id": int(task_id), "tenant_id": int(_core._tid())},
    ).mappings().first()


def deadline_projection(db, task_id: int, *, status: str | None = None) -> dict:
    row = _deadline_row(db, task_id)
    deadline = row.get("deadline_at") if row else None
    state = str(status or "").upper()
    overdue = bool(deadline and state not in _SUBMITTED_STATES and _now() > deadline)
    remaining_seconds = None
    if deadline and state not in _SUBMITTED_STATES:
        remaining_seconds = int((deadline - _now()).total_seconds())
    return {
        "deadlineReady": bool(deadline),
        "deadline": deadline.isoformat() if deadline else None,
        "deadlineUpdatedAt": row.get("deadline_updated_at").isoformat() if row and row.get("deadline_updated_at") else None,
        "isOverdue": overdue if deadline else None,
        "deadlineRemainingSeconds": remaining_seconds,
    }


def extend_deadline(task_id: int, user, deadline_at, reason: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "设置/延期原因不少于5字")
    new_deadline = _parse_deadline(deadline_at)
    now = _now()
    if new_deadline <= now:
        raise AppException("VALIDATION_ERROR", "新截止时间必须晚于当前时间")

    with _core.session() as db:
        task = _grade._load_task(db, int(task_id), lock=True)
        role = str((user or {}).get("currentRoleCode") or "").upper()
        if (user or {}).get("userType") != "PLATFORM_SUPER_ADMIN" and role not in {
            "ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"
        }:
            raise AppException("NO_DATA_SCOPE", "仅教务/学院管理员可设置或延长成绩截止时间", http_status=403)
        _core._check_course_scope(task, user)
        if role == "COLLEGE_ADMIN":
            _core._check_college_scope(db, task, user)
        if str(task.status or "").upper() in _FINAL_STATES:
            raise AppException("DATA_CONFLICT", "成绩已发布/归档，禁止修改截止时间", http_status=409)

        row = _deadline_row(db, int(task_id), lock=True)
        previous = row.get("deadline_at") if row else None
        if previous and new_deadline <= previous:
            raise AppException(
                "VALIDATION_ERROR",
                "延期后的截止时间必须晚于当前截止时间",
                details={"currentDeadline": previous.isoformat()},
            )
        db.execute(
            text(
                "UPDATE t_aa_grade_task "
                "SET deadline_at=:deadline_at, deadline_updated_at=:updated_at, updated_at=:updated_at "
                "WHERE id=:task_id AND tenant_id=:tenant_id AND is_deleted=0"
            ),
            {
                "deadline_at": new_deadline,
                "updated_at": now,
                "task_id": int(task_id),
                "tenant_id": int(_core._tid()),
            },
        )
        action = "GRADE_DEADLINE_EXTEND" if previous else "GRADE_DEADLINE_SET"
        _core._audit(
            db,
            "AA_GRADE_TASK",
            int(task_id),
            action,
            f"from={previous.isoformat() if previous else ''};to={new_deadline.isoformat()};reason={reason}",
        )
        db.commit()
        return {
            "taskId": str(task_id),
            "deadlineReady": True,
            "deadline": new_deadline.isoformat(),
            "previousDeadline": previous.isoformat() if previous else None,
            "isExtension": bool(previous),
            "reason": reason,
        }


def require_submit_within_deadline(task_id: int, user) -> None:
    """Fail closed after a real deadline; tasks without a configured deadline remain compatible."""
    with _core.session() as db:
        _grade._load_task(db, int(task_id), lock=True)
        row = _deadline_row(db, int(task_id), lock=True)
        deadline = row.get("deadline_at") if row else None
        if deadline and _now() > deadline:
            raise AppException(
                "GRADE_DEADLINE_EXPIRED",
                "成绩录入已超过截止时间，请联系学院/教务延期后再提交",
                details={"deadline": deadline.isoformat()},
                http_status=409,
            )


def teacher_submit_task(task_id: int, user) -> dict:
    require_submit_within_deadline(task_id, user)
    return _grade_exec.teacher_submit_task(task_id, user)