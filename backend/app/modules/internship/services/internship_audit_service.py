"""Structured internship audit plus persistent platform audit outbox."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditOutbox, InternshipAuditTrail
from app.models.audit_outbox import stage_outbox_event_id
from app.services.db_service import _tid
from app.services.db_service import session

_SENSITIVE = ("phone", "mobile", "idcard", "id_card", "token", "ip", "contact")


def _sanitize(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(part in key.lower() for part in _SENSITIVE) and item:
                result[key] = "sha256:" + hashlib.sha256(
                    str(item).encode("utf-8")).hexdigest()[:16]
            else:
                result[key] = _sanitize(item)
        return result
    if isinstance(value, list):
        return [_sanitize(x) for x in value]
    return value


def add_audit(db, *, target_type, target_id, action, user=None, batch_id=None,
              internship_id=None, before_status=None, after_status=None,
              expected_version=None, new_version=None, reason=None,
              rule_version=None, file_ids=None, detail=None, event_id=None):
    actor = user or {}
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
    """把 PENDING / 到期 RETRY_WAIT 的审计事件落到安全审计表并标记 PROCESSED。

    此前 t_audit_outbox 只有生产者没有消费者：行会永远停在 PENDING，
    而 health() 只看 DEAD 数，于是"队列从没被消费"表现为健康。
    """
    from app.db.session import get_sessionmaker
    from app.services.db_service import audit_insert_in_session

    now = datetime.utcnow()
    processed = failed = 0
    db = get_sessionmaker()()
    try:
        rows = db.scalars(
            select(AuditOutbox)
            .where(AuditOutbox.status.in_(("PENDING", "RETRY_WAIT")))
            .where((AuditOutbox.next_retry_at.is_(None)) | (AuditOutbox.next_retry_at <= now))
            .order_by(AuditOutbox.id)
            .limit(max(1, int(limit)))
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            try:
                payload = dict(row.payload_json or {})
                audit_insert_in_session(
                    db, row.event_type, str(payload.get("targetType") or "internship"),
                    payload, "SUCCESS",
                    tenant_id=int(row.tenant_id),
                    resource_id=str(payload.get("targetId") or "") or None,
                )
                row.status = "PROCESSED"
                row.processed_at = now
                row.last_error = None
                processed += 1
            except Exception as exc:  # noqa: BLE001 — 单条失败进退避重试，不拖垮整批
                row.retry_count = int(row.retry_count or 0) + 1
                row.last_error = f"{worker_id}: {exc}"[:1000]
                row.status = "DEAD" if row.retry_count >= 10 else "RETRY_WAIT"
                row.next_retry_at = None if row.status == "DEAD" else (
                    now + timedelta(minutes=min(60, 2 ** row.retry_count)))
                failed += 1
        db.commit()
    finally:
        db.close()
    return {"processed": processed, "failed": failed}


def health(db) -> dict:
    rows = dict(db.execute(select(AuditOutbox.status, func.count()).where(
        AuditOutbox.tenant_id == _tid()).group_by(AuditOutbox.status)).all())
    # 积压也是不健康：只看 DEAD 会把"消费者根本没跑"判成健康。
    backlog = int(rows.get("PENDING", 0)) + int(rows.get("RETRY_WAIT", 0))
    oldest_pending = db.scalar(select(func.min(AuditOutbox.created_at)).where(
        AuditOutbox.tenant_id == _tid(),
        AuditOutbox.status.in_(("PENDING", "RETRY_WAIT"))))
    stalled = bool(oldest_pending and (datetime.utcnow() - oldest_pending) > timedelta(hours=1))
    return {"counts": rows, "dead": int(rows.get("DEAD", 0)),
            "backlog": backlog, "stalled": stalled,
            "oldestPendingAt": oldest_pending.isoformat() + "Z" if oldest_pending else None,
            "healthy": int(rows.get("DEAD", 0)) == 0 and not stalled}


def health_status() -> dict:
    with session() as db:
        return health(db)
