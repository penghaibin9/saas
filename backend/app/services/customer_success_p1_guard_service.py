"""Serializable, atomically audited write authority for PLAT-05 customer success.

The legacy customer-health service remains the read/health-score authority. Its mutation
helpers predate concurrent platform operators and commit before platform audit. The P1
workspace routes all writes through this guard so state transitions are row-locked,
optimistic-version checked, state-machine checked, and audited in the same transaction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.customer_success import RenewalTask, SupportTicket, TrainingRecord

_TICKET_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "RESOLVED"},
    "IN_PROGRESS": {"RESOLVED"},
    "RESOLVED": {"IN_PROGRESS", "CLOSED"},
    "CLOSED": set(),
}
_RENEWAL_TRANSITIONS = {
    "PENDING": {"CONTACTED", "COMMITTED", "RENEWED", "CHURNED"},
    "CONTACTED": {"COMMITTED", "RENEWED", "CHURNED"},
    "COMMITTED": {"RENEWED", "CHURNED"},
    "RENEWED": set(),
    "CHURNED": set(),
}


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _actor(user: dict | None) -> str:
    return str((user or {}).get("userId") or (user or {}).get("id") or "")


def _text(value, *, field: str, max_len: int, required_min: int = 0) -> str:
    text = str(value or "").strip()
    if required_min and len(text) < required_min:
        raise AppException("VALIDATION_ERROR", f"{field}不能为空")
    if len(text) > max_len:
        raise AppException("VALIDATION_ERROR", f"{field}最长 {max_len} 个字符")
    return text


def _lock_row(db, model, row_id: int, label: str):
    row = db.scalars(select(model).where(
        model.id == int(row_id), model.is_deleted.is_(False),
    ).with_for_update()).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", f"{label}不存在", http_status=404)
    return row


def _require_version(row, expected_version) -> int:
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "状态变更必须提供 expectedVersion")
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from None
    current = int(row.version or 0)
    if current != expected:
        raise AppException(
            "VERSION_CONFLICT", "记录已被其他平台主管修改，请刷新后重试", http_status=409,
            details={"expectedVersion": expected, "currentVersion": current},
        )
    return current


def _ticket_dto(row: SupportTicket) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "title": row.title,
        "description": row.description or "", "severity": row.severity, "status": row.status,
        "reporterName": row.reporter_name or "", "assigneeUserId": str(row.assignee_user_id or "") or None,
        "assigneeName": row.assignee_name or "", "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolutionNote": row.resolution_note or "", "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _training_dto(row: TrainingRecord) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "topic": row.topic,
        "trainerName": row.trainer_name or "", "scheduledAt": row.scheduled_at.isoformat(),
        "status": row.status, "attendeeCount": int(row.attendee_count or 0),
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "note": row.note or "", "version": int(row.version or 0),
    }


def _renewal_dto(row: RenewalTask) -> dict:
    return {
        "id": str(row.id), "tenantId": str(row.tenant_id), "dueAt": row.due_at.isoformat(),
        "status": row.status, "ownerUserId": str(row.owner_user_id or "") or None,
        "ownerName": row.owner_name or "", "note": row.note or "",
        "lastContactedAt": row.last_contacted_at.isoformat() if row.last_contacted_at else None,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "version": int(row.version or 0),
    }


def create_ticket(*, tenant_id: int, title: str, description: str = "", severity: str = "P2",
                  reporter_name: str = "", user: dict | None = None) -> dict:
    from app.services import audit_log

    title = _text(title, field="工单标题", max_len=200, required_min=2)
    description = _text(description, field="工单描述", max_len=2000)
    reporter_name = _text(reporter_name, field="反馈人", max_len=100)
    severity = str(severity or "P2").upper()
    if severity not in {"P0", "P1", "P2", "P3"}:
        raise AppException("VALIDATION_ERROR", f"不支持的优先级：{severity}")
    db = get_sessionmaker()()
    try:
        row = SupportTicket(
            tenant_id=int(tenant_id), title=title, description=description,
            severity=severity, status="OPEN", reporter_name=reporter_name,
        )
        db.add(row)
        db.flush()
        audit_log.record_critical_in_session(
            db, "PLATFORM_SUPPORT_TICKET_CREATE", f"support-ticket:{row.id}",
            detail={"tenantId": str(tenant_id), "severity": severity, "title": title, "actor": _actor(user)},
            tenant_id=int(tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _ticket_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def transition_ticket(ticket_id: int, *, status: str, resolution_note: str = "",
                      expected_version, user: dict | None = None) -> dict:
    from app.services import audit_log

    target = str(status or "").upper()
    resolution_note = _text(resolution_note, field="处理结论", max_len=2000)
    db = get_sessionmaker()()
    try:
        row = _lock_row(db, SupportTicket, ticket_id, "工单")
        current = str(row.status or "").upper()
        current_version = _require_version(row, expected_version)
        if target not in _TICKET_TRANSITIONS.get(current, set()):
            raise AppException("STATE_TRANSITION_DENIED", f"工单不能从 {current} 变更为 {target}", http_status=409)
        row.status = target
        row.version = current_version + 1
        if target in {"RESOLVED", "CLOSED"}:
            row.resolved_at = _now()
            if resolution_note:
                row.resolution_note = resolution_note
        elif target == "IN_PROGRESS" and current == "RESOLVED":
            # Re-opened work is no longer resolved; preserve note as history but clear the timestamp.
            row.resolved_at = None
        audit_log.record_critical_in_session(
            db, "PLATFORM_SUPPORT_TICKET_TRANSITION", f"support-ticket:{row.id}",
            detail={
                "tenantId": str(row.tenant_id), "before": current, "after": target,
                "expectedVersion": current_version, "newVersion": int(row.version), "actor": _actor(user),
            }, tenant_id=int(row.tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _ticket_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_training(*, tenant_id: int, topic: str, scheduled_at: datetime,
                    trainer_name: str = "", user: dict | None = None) -> dict:
    from app.services import audit_log

    topic = _text(topic, field="培训主题", max_len=200, required_min=2)
    trainer_name = _text(trainer_name, field="培训讲师", max_len=100)
    db = get_sessionmaker()()
    try:
        row = TrainingRecord(
            tenant_id=int(tenant_id), topic=topic, trainer_name=trainer_name,
            scheduled_at=scheduled_at, status="SCHEDULED",
        )
        db.add(row)
        db.flush()
        audit_log.record_critical_in_session(
            db, "PLATFORM_TRAINING_CREATE", f"training:{row.id}",
            detail={"tenantId": str(tenant_id), "topic": topic, "scheduledAt": scheduled_at.isoformat(), "actor": _actor(user)},
            tenant_id=int(tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _training_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def complete_training(training_id: int, *, attendee_count: int, note: str = "",
                      expected_version=None, user: dict | None = None) -> dict:
    from app.services import audit_log

    try:
        count = int(attendee_count)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "参训人数必须是整数") from None
    if count < 0:
        raise AppException("VALIDATION_ERROR", "参训人数不能为负数")
    note = _text(note, field="培训备注", max_len=1000)
    db = get_sessionmaker()()
    try:
        row = _lock_row(db, TrainingRecord, training_id, "培训记录")
        current = str(row.status or "").upper()
        current_version = _require_version(row, expected_version)
        if current != "SCHEDULED":
            raise AppException("STATE_TRANSITION_DENIED", f"培训处于 {current}，不能标记完成", http_status=409)
        row.status = "COMPLETED"
        row.attendee_count = count
        row.completed_at = _now()
        if note:
            row.note = note
        row.version = current_version + 1
        audit_log.record_critical_in_session(
            db, "PLATFORM_TRAINING_COMPLETE", f"training:{row.id}",
            detail={
                "tenantId": str(row.tenant_id), "attendeeCount": count,
                "expectedVersion": current_version, "newVersion": int(row.version), "actor": _actor(user),
            }, tenant_id=int(row.tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _training_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_renewal_task(*, tenant_id: int, due_at: datetime, owner_name: str = "",
                        note: str = "", user: dict | None = None) -> dict:
    from app.services import audit_log

    owner_name = _text(owner_name, field="跟进负责人", max_len=100)
    note = _text(note, field="跟进备注", max_len=1000)
    db = get_sessionmaker()()
    try:
        row = RenewalTask(
            tenant_id=int(tenant_id), due_at=due_at, status="PENDING",
            owner_name=owner_name, note=note,
        )
        db.add(row)
        db.flush()
        audit_log.record_critical_in_session(
            db, "PLATFORM_RENEWAL_TASK_CREATE", f"renewal-task:{row.id}",
            detail={"tenantId": str(tenant_id), "dueAt": due_at.isoformat(), "ownerName": owner_name, "actor": _actor(user)},
            tenant_id=int(tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _renewal_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def transition_renewal_task(task_id: int, *, status: str, note: str = "",
                            expected_version=None, user: dict | None = None) -> dict:
    from app.services import audit_log

    target = str(status or "").upper()
    note = _text(note, field="续费跟进备注", max_len=1000)
    db = get_sessionmaker()()
    try:
        row = _lock_row(db, RenewalTask, task_id, "续费任务")
        current = str(row.status or "").upper()
        current_version = _require_version(row, expected_version)
        if target not in _RENEWAL_TRANSITIONS.get(current, set()):
            raise AppException("STATE_TRANSITION_DENIED", f"续费任务不能从 {current} 变更为 {target}", http_status=409)
        row.status = target
        row.version = current_version + 1
        if note:
            row.note = note
        if target == "CONTACTED":
            row.last_contacted_at = _now()
        if target in {"RENEWED", "CHURNED"}:
            row.closed_at = _now()
        audit_log.record_critical_in_session(
            db, "PLATFORM_RENEWAL_TASK_TRANSITION", f"renewal-task:{row.id}",
            detail={
                "tenantId": str(row.tenant_id), "before": current, "after": target,
                "expectedVersion": current_version, "newVersion": int(row.version), "actor": _actor(user),
            }, tenant_id=int(row.tenant_id), resource_id=str(row.id),
        )
        db.commit()
        db.refresh(row)
        return _renewal_dto(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
