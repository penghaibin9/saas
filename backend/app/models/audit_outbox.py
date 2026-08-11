"""Reliable platform audit outbox written in the same transaction as business facts."""
from __future__ import annotations

from datetime import datetime
import hashlib
import uuid

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.base import AuditTimeMixin, Base, PKMixin, TenantMixin


class AuditOutbox(PKMixin, TenantMixin, AuditTimeMixin, Base):
    __tablename__ = "t_audit_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", name="uk_audit_outbox_event"),
    )

    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING/PROCESSING/PROCESSED/RETRY_WAIT/DEAD")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(1000))


def _safe(value):
    sensitive = ("phone", "mobile", "idcard", "id_card", "token", "client_ip", "contact")
    if isinstance(value, dict):
        return {
            key: ("sha256:" + hashlib.sha256(str(item).encode()).hexdigest()[:16]
                  if item and any(part in key.lower() for part in sensitive)
                  else _safe(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


# 一次业务审计 = 恰好一条 outbox 事件。
# 服务层若需要拿到 event_id（用于 mark_processed / mark_retry），不要自己再 db.add 一条
# AuditOutbox —— 那会和本监听器各写一条、event_id 还不一样，等于同一事实入队两次。
# 正确做法：调用 stage_outbox_event_id() 把 event_id 预挂到 trail 上，由本监听器统一入队。
_STAGED_EVENT_ID = "_audit_outbox_event_id"


def stage_outbox_event_id(trail, event_id: str | None = None) -> str:
    """给一条待写入的审计 trail 预分配 outbox event_id，并返回它。"""
    eid = event_id or uuid.uuid4().hex
    setattr(trail, _STAGED_EVENT_ID, eid)
    return eid


@event.listens_for(Session, "before_flush")
def enqueue_internship_trails(db, _flush_context, _instances):
    """Every new internship trail gets exactly one durable outbox row in the same transaction."""
    from app.models.internship import InternshipAuditTrail
    trails = [row for row in list(db.new) if isinstance(row, InternshipAuditTrail)]
    for trail in trails:
        detail = _safe(trail.detail_json or {})
        db.add(AuditOutbox(
            tenant_id=trail.tenant_id,
            event_id=getattr(trail, _STAGED_EVENT_ID, None) or uuid.uuid4().hex,
            event_type=f"INTERNSHIP_{trail.action}",
            payload_json={
                "action": trail.action, "targetType": trail.target_type,
                "targetId": str(trail.target_id), "tenantId": str(trail.tenant_id),
                "batchId": detail.get("batchId"), "internshipId": detail.get("internshipId"),
                "actorUserId": detail.get("actorUserId"),
                "actorName": trail.operator_name,
                "actorRole": detail.get("actorRole"),
                "beforeStatus": detail.get("beforeStatus"),
                "afterStatus": detail.get("afterStatus"),
                "expectedVersion": detail.get("expectedVersion"),
                "newVersion": detail.get("newVersion"),
                "reason": detail.get("reason"),
                "ruleVersion": detail.get("ruleVersion"),
                "fileIds": detail.get("fileIds") or detail.get("evidenceFileIds") or [],
                "detailJson": detail,
                "occurredAt": (trail.occurred_at or datetime.utcnow()).isoformat() + "Z",
            }, status="PENDING"))
