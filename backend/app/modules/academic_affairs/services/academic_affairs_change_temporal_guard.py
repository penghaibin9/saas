"""Stage C1 future-effective academic status changes.

Approval and application are different facts. A final approval whose business
``effective_date`` is still in the future becomes ``APPROVED_PENDING_EFFECTIVE``;
the scheduled worker applies it exactly once at/after that timestamp through the
same ``change_student_status -> append_student_academic_fact`` canonical path.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import event, select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services.db_service import _tid

from . import academic_affairs_change_service as change_service

_SELECTED_EFFECTIVE_AT: ContextVar[datetime | None] = ContextVar(
    "aa_status_change_selected_effective_at", default=None
)

_ORIGINAL_PUBLIC_SUBMIT = change_service.submit
_ORIGINAL_REVIEW_IN_SESSION = change_service.review_in_session


def _parse_future_effective(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "effectiveDate 必须是 ISO-8601 日期时间") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    if parsed <= datetime.utcnow():
        raise AppException("VALIDATION_ERROR", "计划生效时间必须晚于当前时间")
    return parsed


def _freeze_effective_date(_mapper, _connection, target) -> None:
    selected = _SELECTED_EFFECTIVE_AT.get()
    if selected is None:
        return
    existing = getattr(target, "effective_date", None)
    if existing is not None and existing != selected:
        raise AppException(
            "EFFECTIVE_DATE_CONFLICT",
            "异动计划生效时间在写入过程中发生冲突",
            http_status=409,
        )
    target.effective_date = selected


@wraps(_ORIGINAL_PUBLIC_SUBMIT)
def temporal_submit(body, user) -> dict:
    selected = _parse_future_effective(getattr(body, "effectiveDate", None))
    token = _SELECTED_EFFECTIVE_AT.set(selected)
    try:
        return _ORIGINAL_PUBLIC_SUBMIT(body, user)
    finally:
        _SELECTED_EFFECTIVE_AT.reset(token)


def _pending_future_final(db, sc_id, user, action, reason=""):
    """Handle only the final APPROVE whose effective time is still in the future."""
    from app.models import StudentProfile, WorkflowInstance, WorkflowTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import (
        guard_term_writable_current,
    )

    if str(action or "").upper() != "APPROVE":
        return None
    x, s = change_service._load(db, sc_id, lock=True)
    nodes = change_service.CHANGE_FLOW[x.change_type][1]
    due_at = x.effective_date
    if not due_at or due_at <= datetime.utcnow() or x.current_node != nodes[-1]:
        return None

    guard_term_writable_current(db)
    if x.status not in change_service._ACTIVE and x.status != "IN_REVIEW":
        raise AppException("APPROVAL_VERSION_CONFLICT", "该异动当前状态不可审批")
    change_service._check_node_authority(db, user, x.current_node, x)

    student = db.query(StudentProfile).filter(
        StudentProfile.id == int(x.student_id),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update().first()
    if not student:
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    if x.expected_student_version is None:
        raise AppException(
            "STATUS_CHANGE_VERSION_SNAPSHOT_MISSING",
            "异动单缺少发起时学生版本，禁止审批为未来生效",
            http_status=409,
        )
    if int(student.version or 0) != int(x.expected_student_version):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "学生主档在申请在途期间已被改写，禁止批准过期的未来生效异动",
            details={
                "expectedVersion": int(x.expected_student_version),
                "currentVersion": int(student.version or 0),
            },
            http_status=409,
        )

    inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.instance_id == (inst.id if inst else 0),
        WorkflowTask.node_code == x.current_node,
        WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).with_for_update()).first() if inst else None
    if not task:
        raise AppException("APPROVAL_VERSION_CONFLICT", "当前终审任务不存在或已被处理", http_status=409)

    task.status = "APPROVED"
    task.acted_at = datetime.utcnow()
    if inst:
        inst.status = "APPROVED"
        inst.current_node = None
    x.status = "APPROVED_PENDING_EFFECTIVE"
    x.current_node = None
    x.current_task_id = None
    x.version = int(x.version or 0) + 1
    x.decision_version = int(x.decision_version or 0) + 1
    change_service._todo_done(db, x.id)
    change_service._msg(
        db,
        x.student_id,
        f"{change_service.L_CT[x.change_type]}已审批，待生效",
        f"你的{change_service.L_CT[x.change_type]}申请已审批通过，将于 {due_at.isoformat()} 生效",
        "WORKFLOW_RESULT",
        x.id,
    )
    change_service._audit(db, x.id, "APPROVED_PENDING_EFFECTIVE", due_at.isoformat())
    db.flush()
    return change_service._row(x, s), {"outbox": True}


def temporal_review_in_session(db, sc_id, user, action, reason=""):
    pending = _pending_future_final(db, sc_id, user, action, reason)
    if pending is not None:
        return pending
    return _ORIGINAL_REVIEW_IN_SESSION(db, sc_id, user, action, reason)


def apply_one_due_change(change_id: int) -> dict:
    """Apply one due approved change exactly once for the current tenant context."""
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_status_service import (
        audit_status_change,
        change_student_status,
    )

    db = get_sessionmaker()()
    post = None
    try:
        x = db.query(AaStatusChange).filter(
            AaStatusChange.id == int(change_id),
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.is_deleted.is_(False),
        ).with_for_update().first()
        if not x or x.status != "APPROVED_PENDING_EFFECTIVE":
            db.rollback()
            return {"changeId": str(change_id), "status": "SKIPPED"}
        if not x.effective_date or x.effective_date > datetime.utcnow():
            db.rollback()
            return {"changeId": str(change_id), "status": "NOT_DUE"}

        res = change_student_status(
            db,
            x.student_id,
            x.to_status,
            change_type=x.change_type,
            reason=x.reason or "",
            operator="0",
            existing_change_id=x.id,
            to_college_id=x.to_college_id,
            to_major_id=x.to_major_id,
            to_class_id=x.to_class_id,
            expected_student_version=x.expected_student_version,
            effective_at=x.effective_date,
        )
        x.version = int(x.version or 0) + 1
        change_service._msg(
            db,
            x.student_id,
            f"{change_service.L_CT[x.change_type]}已生效",
            f"你的{change_service.L_CT[x.change_type]}申请已按计划生效",
            "WORKFLOW_RESULT",
            x.id,
        )
        change_service._audit(
            db, x.id, "EFFECTIVE", f"{res['fromStatus']}->{res['toStatus']}@{res['effectiveAt']}"
        )
        db.commit()
        post = res
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services.message_event_outbox_service import try_process_pending_outbox

    try_process_pending_outbox(worker_id="aa-future-effective")
    audit_status_change(
        post["studentId"], post["fromStatus"], post["toStatus"], post["changeType"], "SYSTEM"
    )
    return {"changeId": str(change_id), "status": "EFFECTIVE", **post}


def apply_due_changes(limit: int = 100) -> dict:
    """Scan due ids, then apply each in its own transaction for failure isolation."""
    from app.models import AaStatusChange

    db = get_sessionmaker()()
    try:
        ids = list(db.scalars(select(AaStatusChange.id).where(
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.status == "APPROVED_PENDING_EFFECTIVE",
            AaStatusChange.effective_date.is_not(None),
            AaStatusChange.effective_date <= datetime.utcnow(),
            AaStatusChange.is_deleted.is_(False),
        ).order_by(AaStatusChange.effective_date, AaStatusChange.id).limit(max(1, min(int(limit), 500)))))
    finally:
        db.close()

    applied = skipped = failed = 0
    errors = []
    for change_id in ids:
        try:
            result = apply_one_due_change(int(change_id))
            if result.get("status") == "EFFECTIVE":
                applied += 1
            else:
                skipped += 1
        except AppException as exc:
            failed += 1
            errors.append({"changeId": str(change_id), "code": exc.code})
        except Exception as exc:  # scheduler caller records full exception metrics
            failed += 1
            errors.append({"changeId": str(change_id), "code": type(exc).__name__})
    return {"selected": len(ids), "applied": applied, "skipped": skipped, "failed": failed, "errors": errors}


def install() -> None:
    from app.models import AaStatusChange

    if not event.contains(AaStatusChange, "before_insert", _freeze_effective_date):
        event.listen(AaStatusChange, "before_insert", _freeze_effective_date)

    if not hasattr(change_service, "_stage_c1_pre_temporal_submit"):
        change_service._stage_c1_pre_temporal_submit = change_service.submit
    if not hasattr(change_service, "_stage_c1_pre_temporal_review_in_session"):
        change_service._stage_c1_pre_temporal_review_in_session = change_service.review_in_session

    if not getattr(change_service.submit, "_stage_c1_temporal_guard", False):
        temporal_submit._stage_c1_temporal_guard = True
        change_service.submit = temporal_submit
    if not getattr(change_service.review_in_session, "_stage_c1_temporal_guard", False):
        temporal_review_in_session._stage_c1_temporal_guard = True
        change_service.review_in_session = temporal_review_in_session
