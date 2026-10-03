"""岗位实习 Standalone 业务消息 Outbox。

仅保留岗位实习实际使用的事件。业务事务写 outbox；提交后可同步尽力消费，
失败保留 RETRY_WAIT，不伪造成功。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.models import MessageCampaign, MessageEventOutbox, StudentProfile, UnifiedMessage, User
from app.services import student_account_link_service as link_svc
from app.services.db_service import _tid, session

log = logging.getLogger("internship.message_outbox")

_EVENT_TEMPLATES = {
    "INTERNSHIP.COUNSELOR_NOTICE": ("BUSINESS", "NORMAL", "实习辅导员通知"),
    "INTERNSHIP.WEEKLY_REMIND": ("REMINDER", "IMPORTANT", "实习周报提醒"),
    "INTERNSHIP.WEEKLY_RETURNED": ("BUSINESS", "IMPORTANT", "实习周报已退回"),
    "INTERNSHIP.WEEKLY_APPROVED": ("BUSINESS", "NORMAL", "实习周报已通过"),
    "INTERNSHIP.RISK_CREATED": ("WARNING", "IMPORTANT", "实习风险提醒"),
    "INTERNSHIP.RISK_REMINDED": ("REMINDER", "IMPORTANT", "实习风险催办"),
    "INTERNSHIP.VOLUNTEER.SCHOOL_RESULT": ("BUSINESS", "IMPORTANT", "岗位志愿办理结果"),
    "INTERNSHIP.POSITION.RETURNED": ("TODO", "IMPORTANT", "岗位资料待补正"),
    "INTERNSHIP.POSITION.PUBLISHED": ("BUSINESS", "NORMAL", "岗位已通过并上架"),
    "INTERNSHIP.POSITION.STATUS_CHANGED": ("BUSINESS", "IMPORTANT", "岗位状态已调整"),
}
_MAX_ATTEMPTS = 8


def emit_message_event(
    db,
    *,
    event_code: str,
    source_module: str,
    source_biz_type: str,
    source_biz_id: int,
    recipient_refs: list[dict],
    variables: dict | None = None,
    action_key: str | None = None,
    action_params: dict | None = None,
    dedup_key: str | None = None,
    content: str | None = None,
    title: str | None = None,
    tenant_id: int | None = None,
):
    code = str(event_code or "").strip().upper()
    if code not in _EVENT_TEMPLATES:
        raise AppException("VALIDATION_ERROR", f"未登记的岗位实习消息事件码：{code}", http_status=422)
    if not recipient_refs:
        raise AppException("VALIDATION_ERROR", "recipient_refs 不能为空", http_status=422)
    effective_tenant = int(tenant_id or _tid())
    key = str(dedup_key or f"{code}:{source_biz_type}:{int(source_biz_id)}")[:120]
    existed = db.scalar(select(MessageEventOutbox).where(
        MessageEventOutbox.tenant_id == effective_tenant,
        MessageEventOutbox.dedup_key == key,
        MessageEventOutbox.is_deleted.is_(False),
    ))
    if existed:
        return existed
    category, priority, default_title = _EVENT_TEMPLATES[code]
    row = MessageEventOutbox(
        tenant_id=effective_tenant,
        event_code=code,
        source_module=source_module or "internship",
        source_biz_type=str(source_biz_type or "INTERNSHIP"),
        source_biz_id=int(source_biz_id),
        payload_json={
            "title": str(title or default_title)[:500],
            "content": str(content or "")[:2000],
            "variables": dict(variables or {}),
            "actionKey": action_key,
            "actionParams": dict(action_params or {}),
            "category": category,
            "priority": priority,
        },
        recipient_refs_json=list(recipient_refs),
        dedup_key=key,
        status="PENDING",
        attempt_count=0,
        occurred_at=datetime.utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existed = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == effective_tenant,
            MessageEventOutbox.dedup_key == key,
            MessageEventOutbox.is_deleted.is_(False),
        ))
        if existed:
            return existed
        raise
    return row


def emit_receiver_notice(
    db,
    *,
    event_code: str,
    source_module: str,
    source_biz_type: str,
    source_biz_id: int,
    receiver_id: int,
    title: str,
    content: str,
    receiver_as: str = "student",
    action_key: str | None = None,
    action_params: dict | None = None,
    dedup_extra: str = "",
):
    rid = int(receiver_id or 0)
    if rid <= 0:
        return None
    refs = [{"userId": rid}] if receiver_as == "user" else [{"studentId": rid}]
    return emit_message_event(
        db,
        event_code=event_code,
        source_module=source_module,
        source_biz_type=source_biz_type,
        source_biz_id=int(source_biz_id),
        recipient_refs=refs,
        title=title,
        content=content,
        action_key=action_key,
        action_params=action_params,
        dedup_key=f"{event_code}:{source_biz_type}:{source_biz_id}:{receiver_as}:{rid}:{dedup_extra}"[:120],
    )


def _resolve_user_id(db, tenant_id: int, ref: dict) -> tuple[int | None, str]:
    uid = ref.get("userId") or ref.get("user_id")
    if uid:
        try:
            value = int(uid)
        except (TypeError, ValueError):
            return None, "UNKNOWN"
        exists = db.scalar(select(User.id).where(
            User.id == value,
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        ))
        return (int(exists), str(ref.get("receiverType") or "STAFF").upper()) if exists else (None, "UNKNOWN")

    sid = ref.get("studentId") or ref.get("student_id")
    if not sid:
        return None, "UNKNOWN"
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == int(sid),
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    ))
    if not student:
        return None, "UNKNOWN"
    uid = link_svc.resolve_user_id_for_student(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        student_no=student.student_no,
        require_active_account=True,
    )
    return (uid, "STUDENT") if uid else (None, "UNKNOWN")


def _deliver(db, row: MessageEventOutbox) -> None:
    payload = dict(row.payload_json or {})
    category = str(payload.get("category") or "BUSINESS")
    priority = str(payload.get("priority") or "NORMAL")
    idem = f"outbox:{row.id}"
    campaign = db.scalar(select(MessageCampaign).where(
        MessageCampaign.tenant_id == row.tenant_id,
        MessageCampaign.idempotency_key == idem,
        MessageCampaign.is_deleted.is_(False),
    ))
    if campaign is None:
        campaign = MessageCampaign(
            tenant_id=row.tenant_id,
            title=str(payload.get("title") or row.event_code)[:200],
            content_plain=str(payload.get("content") or "")[:2000],
            category=category,
            priority=priority,
            status="PUBLISHED",
            source_kind="BUSINESS_EVENT",
            source_module=row.source_module,
            source_biz_type=row.source_biz_type,
            source_biz_id=row.source_biz_id,
            sender_user_id=0,
            publish_mode="IMMEDIATE",
            published_at=datetime.utcnow(),
            effective_at=datetime.utcnow(),
            action_key=payload.get("actionKey"),
            action_params_json=dict(payload.get("actionParams") or {}),
            idempotency_key=idem,
            recipient_count=0,
            delivered_count=0,
        )
        db.add(campaign)
        db.flush()

    delivered = 0
    for ref in row.recipient_refs_json or []:
        if not isinstance(ref, dict):
            continue
        uid, receiver_type = _resolve_user_id(db, row.tenant_id, ref)
        if not uid:
            continue
        existed = db.scalar(select(UnifiedMessage.id).where(
            UnifiedMessage.tenant_id == row.tenant_id,
            UnifiedMessage.campaign_id == campaign.id,
            UnifiedMessage.receiver_user_id == uid,
            UnifiedMessage.receiver_context_key == "GLOBAL",
            UnifiedMessage.is_deleted.is_(False),
        ))
        if existed:
            delivered += 1
            continue
        db.add(UnifiedMessage(
            tenant_id=row.tenant_id,
            receiver_id=uid,
            receiver_user_id=uid,
            receiver_type=receiver_type,
            receiver_context_key="GLOBAL",
            source_module=row.source_module,
            source_biz_id=row.source_biz_id,
            title=str(payload.get("title") or row.event_code)[:500],
            content=str(payload.get("content") or "")[:2000],
            message_type="WORKFLOW_RESULT" if category == "BUSINESS" else category,
            status="UNREAD",
            campaign_id=campaign.id,
            priority=priority,
            category=category,
            delivered_at=datetime.utcnow(),
            require_ack=False,
            action_key=payload.get("actionKey"),
            action_params_json=dict(payload.get("actionParams") or {}),
            delivery_status="DELIVERED",
        ))
        delivered += 1
    campaign.recipient_count = max(int(campaign.recipient_count or 0), delivered)
    campaign.delivered_count = max(int(campaign.delivered_count or 0), delivered)


def process_pending_outbox(limit: int = 30, worker_id: str = "internship", *, outbox_ids: list[int] | None = None) -> int:
    now = datetime.utcnow()
    processed = 0
    with session() as db:
        query = select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.is_deleted.is_(False),
            MessageEventOutbox.status.in_(("PENDING", "RETRY_WAIT")),
            or_(MessageEventOutbox.next_retry_at.is_(None), MessageEventOutbox.next_retry_at <= now),
        )
        if outbox_ids:
            query = query.where(MessageEventOutbox.id.in_([int(x) for x in outbox_ids]))
        rows = db.scalars(query.order_by(MessageEventOutbox.id).limit(max(1, int(limit))).with_for_update()).all()
        for row in rows:
            try:
                row.status = "PROCESSING"
                row.locked_by = str(worker_id)[:80]
                row.locked_at = now
                row.attempt_count = int(row.attempt_count or 0) + 1
                _deliver(db, row)
                row.status = "SUCCEEDED"
                row.processed_at = datetime.utcnow()
                row.next_retry_at = None
                row.last_error_code = None
                processed += 1
            except Exception as exc:
                row.status = "DEAD" if int(row.attempt_count or 0) >= _MAX_ATTEMPTS else "RETRY_WAIT"
                row.last_error_code = type(exc).__name__[:80]
                row.next_retry_at = datetime.utcnow() + timedelta(seconds=min(3600, 30 * (2 ** max(0, row.attempt_count - 1))))
                log.exception("internship outbox delivery failed id=%s", row.id)
        db.commit()
    return processed


def try_process_pending_outbox(limit: int = 30, worker_id: str = "internship-inline", *, outbox_ids: list[int] | None = None) -> None:
    try:
        process_pending_outbox(limit=limit, worker_id=worker_id, outbox_ids=outbox_ids)
    except Exception:
        log.exception("internship inline outbox drain failed")
