"""Structured internship audit plus persistent platform audit outbox."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditOutbox, InternshipAuditTrail
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
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=int(target_id), target_type=target_type,
        action=action, operator_name=payload["actorName"], detail_json=payload,
        occurred_at=datetime.utcnow()))
    eid = event_id or uuid.uuid4().hex
    db.add(AuditOutbox(
        tenant_id=_tid(), event_id=eid, event_type=f"INTERNSHIP_{action}",
        payload_json=payload, status="PENDING"))
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


def health(db) -> dict:
    rows = dict(db.execute(select(AuditOutbox.status, func.count()).where(
        AuditOutbox.tenant_id == _tid()).group_by(AuditOutbox.status)).all())
    return {"counts": rows, "dead": int(rows.get("DEAD", 0)),
            "healthy": int(rows.get("DEAD", 0)) == 0}


def health_status() -> dict:
    with session() as db:
        return health(db)
