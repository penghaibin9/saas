"""Structured internship audit plus persistent platform audit outbox."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditOutbox, InternshipAuditTrail
from app.models.audit_outbox import stage_outbox_event_id
from app.core.exceptions import AppException
from app.services.db_service import _tid
from app.services.db_service import session

from app.core.audit_payload import sanitize_audit_payload as _sanitize
from app.core.context import get_current_user_ctx, get_request_meta, get_trace_id


def add_audit(db, *, target_type, target_id, action, user=None, batch_id=None,
              internship_id=None, before_status=None, after_status=None,
              expected_version=None, new_version=None, reason=None,
              rule_version=None, file_ids=None, detail=None, event_id=None):
    actor = user if user is not None else (get_current_user_ctx() or {})
    payload = _sanitize({
        "action": action, "targetType": target_type, "targetId": str(target_id),
        "tenantId": str(_tid()), "batchId": str(batch_id or ""),
        "internshipId": str(internship_id or ""),
        "actorUserId": str(actor.get("userId") or ""),
        "actorName": actor.get("realName") or "系统",
        "actorRole": actor.get("currentRoleCode") or actor.get("userType") or "",
        "beforeStatus": before_status, "afterStatus": after_status,
        "expectedVersion": expected_version, "newVersion": new_version,
        "reason": reason, "ruleVersion": rule_version, "fileIds": file_ids or [],
        "requestMeta": {**get_request_meta(), "traceId": get_trace_id()},
        "detailJson": detail or {}, "occurredAt": datetime.utcnow().isoformat() + "Z",
    })
    trail = InternshipAuditTrail(
        tenant_id=_tid(), target_id=int(target_id), target_type=target_type,
        action=action, operator_name=payload["actorName"], detail_json=payload,
        occurred_at=datetime.utcnow())
    # outbox 行由 audit_outbox 的 before_flush 监听器统一写入（一条 trail 恰好一条事件）。
    # 这里只预挂 event_id 供调用方后续 mark_processed / mark_retry 使用；
    # 若在此再 db.add(AuditOutbox(...))，同一审计事实会入队两次。
    eid = stage_outbox_event_id(trail, event_id)
    db.add(trail)
    return eid


def add_platform_event(db, *, target_type, target_id, action, actor_name="系统",
                       detail=None, event_id=None):
    payload = _sanitize({
        "action": action, "targetType": target_type, "targetId": str(target_id),
        "tenantId": str(_tid()), "actorName": actor_name,
        "detailJson": detail or {}, "occurredAt": datetime.utcnow().isoformat() + "Z",
    })
    eid = event_id or uuid.uuid4().hex
    db.add(AuditOutbox(
        tenant_id=_tid(), event_id=eid, event_type=f"INTERNSHIP_{action}",
        payload_json=payload, status="PENDING"))
    return eid


def mark_processed(db, event_id: str):
    row = db.scalar(select(AuditOutbox).where(
        AuditOutbox.tenant_id == _tid(), AuditOutbox.event_id == event_id).with_for_update())
    if row and row.status != "PROCESSED":
        row.status = "PROCESSED"
        row.processed_at = datetime.utcnow()


def mark_retry(db, event_id: str, error: str):
    row = db.scalar(select(AuditOutbox).where(
        AuditOutbox.tenant_id == _tid(), AuditOutbox.event_id == event_id).with_for_update())
    if not row or row.status == "PROCESSED":
        return
    row.retry_count = int(row.retry_count or 0) + 1
    row.last_error = str(error)[:1000]
    row.status = "DEAD" if row.retry_count >= 10 else "RETRY_WAIT"
    row.next_retry_at = None if row.status == "DEAD" else (
        datetime.utcnow() + timedelta(minutes=min(60, 2 ** row.retry_count)))


def process_pending(limit: int = 50, worker_id: str = "audit-outbox") -> dict:
    """Lock due rows, isolate poison records, commit each sink fact with its delivery state."""
    from app.db.session import get_sessionmaker
    from app.models.audit import SecurityAuditLog
    from app.services.db_service import audit_insert_in_session

    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("audit batch size must be an integer in 1..1000")
    now = datetime.utcnow()
    processed = failed = 0
    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(AuditOutbox)
            .where(AuditOutbox.status.in_(("PENDING", "RETRY_WAIT")))
            .where((AuditOutbox.next_retry_at.is_(None)) | (AuditOutbox.next_retry_at <= now))
            .order_by(AuditOutbox.id).limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            try:
                # Flush inside SAVEPOINT: deferred MySQL errors must not poison the batch.
                with db.begin_nested():
                    payload = row.payload_json
                    if not isinstance(payload, dict):
                        raise ValueError("Audit payload must be an object")
                    if payload.get("tenantId") not in (None, "") and str(payload["tenantId"]) != str(row.tenant_id):
                        raise ValueError("Audit payload tenant does not match its trusted envelope")
                    existing = db.scalar(select(SecurityAuditLog.id).where(
                        SecurityAuditLog.tenant_id == row.tenant_id,
                        SecurityAuditLog.source_event_id == row.event_id))
                    if existing is None:
                        audit_insert_in_session(
                            db, row.event_type, str(payload.get("targetType") or "internship"),
                            payload, "SUCCESS", tenant_id=int(row.tenant_id),
                            resource_id=str(payload.get("targetId") or "") or None,
                            actor_override={"userId": payload.get("actorUserId"),
                                            "realName": payload.get("actorName"),
                                            "currentRoleCode": payload.get("actorRole")},
                            request_meta_override=payload.get("requestMeta") or {},
                            source_event_id=row.event_id,
                        )
                    row.status = "PROCESSED"
                    row.processed_at = now
                    row.last_error = None
                    row.next_retry_at = None
                    db.flush()
                processed += 1
            except Exception as exc:
                row.retry_count = int(row.retry_count or 0) + 1
                # SQL exception messages can contain bound payloads, credentials and personal data.
                row.last_error = f"AUDIT_DELIVERY_FAILED:{type(exc).__name__}"[:1000]
                row.status = "DEAD" if row.retry_count >= 10 else "RETRY_WAIT"
                row.next_retry_at = None if row.status == "DEAD" else (
                    now + timedelta(minutes=min(60, 2 ** row.retry_count)))
                failed += 1
        db.commit()
    return {"processed": processed, "failed": failed}


def _queue_health(db, tenant_id: int | None) -> dict:
    counts_query = select(AuditOutbox.status, func.count()).group_by(AuditOutbox.status)
    pending_query = select(func.min(AuditOutbox.created_at)).where(
        AuditOutbox.status.in_(("PENDING", "RETRY_WAIT")))
    if tenant_id is not None:
        counts_query = counts_query.where(AuditOutbox.tenant_id == tenant_id)
        pending_query = pending_query.where(AuditOutbox.tenant_id == tenant_id)
    rows = dict(db.execute(counts_query).all())
    backlog = int(rows.get("PENDING", 0)) + int(rows.get("RETRY_WAIT", 0))
    oldest_pending = db.scalar(pending_query)
    stalled = bool(oldest_pending and (datetime.utcnow() - oldest_pending) > timedelta(hours=1))
    return {"counts": rows, "dead": int(rows.get("DEAD", 0)),
            "backlog": backlog, "stalled": stalled,
            "oldestPendingAt": oldest_pending.isoformat() + "Z" if oldest_pending else None,
            "healthy": int(rows.get("DEAD", 0)) == 0 and not stalled}


def health(db) -> dict:
    return _queue_health(db, _tid())


def delivery_health() -> dict:
    """Process-internal aggregate only; authenticated APIs stay tenant scoped."""
    with session() as db:
        return _queue_health(db, None)


def health_status() -> dict:
    with session() as db:
        return health(db)


def assert_high_risk_write_available(db) -> dict:
    """Fail closed before a high-risk internship mutation when audit delivery is unhealthy.

    A fresh PENDING event is normal asynchronous delivery.  DEAD rows or a queue stalled for
    more than one hour mean that another safety-critical write would create an unauditable
    business fact, so the caller must abort the surrounding transaction.
    """
    status = health(db)
    if not status["healthy"]:
        raise AppException(
            "AUDIT_STORE_UNAVAILABLE",
            "审计链路异常，已阻止高风险操作；请先恢复审计队列后重试",
            details={
                "dead": status["dead"],
                "backlog": status["backlog"],
                "stalled": status["stalled"],
                "oldestPendingAt": status["oldestPendingAt"],
            },
            http_status=503,
        )
    return status
