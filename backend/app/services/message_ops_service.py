"""消息中心扩展：模板 CRUD、渠道投递任务、对账告警。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found, no_permission
from app.core.permissions import has_permission
from app.services.db_service import _iso, _tid, session


def _can_manage_tpl(user: dict) -> bool:
    return any(has_permission(user, c) for c in (
        "workbench.message.template.manage",
        "workbench.message.schoolAll.publish",
        "*",
    ))


def _uid(user: dict | None) -> int:
    raw = str((user or {}).get("userId") or "")
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def create_message_template(user: dict, body: dict) -> dict:
    if not _can_manage_tpl(user):
        raise no_permission("无模板管理权限")
    from app.models import NotificationTemplate
    code = (body.get("templateCode") or "").strip().upper()
    content = (body.get("content") or "").strip()
    channel = str(body.get("channel") or "IN_APP").upper()
    if len(code) < 2 or not content:
        raise AppException("VALIDATION_ERROR", "模板编码与正文必填", http_status=422)
    with session() as db:
        existed = db.scalar(select(NotificationTemplate).where(
            NotificationTemplate.tenant_id == _tid(),
            NotificationTemplate.template_code == code,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_deleted.is_(False),
        ))
        if existed:
            raise AppException("DATA_CONFLICT", "同渠道模板编码已存在")
        row = NotificationTemplate(
            tenant_id=_tid(),
            template_code=code,
            channel=channel,
            title=(body.get("title") or code)[:200],
            content=content[:1000],
            enabled=bool(body.get("enabled", True)),
            event_code=body.get("eventCode"),
            template_version=str(body.get("version") or "2026.1"),
            variables_json=body.get("variables") or [],
            locked_fields_json=body.get("lockedFields") or [],
            created_by=_uid(user),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"templateId": str(row.id), "templateCode": row.template_code, "enabled": row.enabled}


def update_message_template(user: dict, template_id: str, body: dict) -> dict:
    if not _can_manage_tpl(user):
        raise no_permission("无模板管理权限")
    from app.models import NotificationTemplate
    with session() as db:
        row = db.scalar(select(NotificationTemplate).where(
            NotificationTemplate.id == int(template_id),
            NotificationTemplate.tenant_id == _tid(),
            NotificationTemplate.is_deleted.is_(False),
        ))
        if not row:
            raise not_found("模板不存在")
        if "title" in body and body["title"] is not None:
            row.title = str(body["title"])[:200]
        if "content" in body and body["content"] is not None:
            row.content = str(body["content"])[:1000]
        if "enabled" in body and body["enabled"] is not None:
            row.enabled = bool(body["enabled"])
        if "variables" in body:
            row.variables_json = body["variables"]
        row.version = int(row.version or 0) + 1
        db.commit()
        return {
            "templateId": str(row.id),
            "templateCode": row.template_code,
            "enabled": bool(row.enabled),
            "title": row.title,
        }


def enqueue_channel_delivery(user: dict, campaign_id: str, *, channel: str) -> dict:
    """外部渠道真发：写入 NotificationTask；未配置则 SKIPPED，不假成功。"""
    from app.models import MessageCampaign, NotificationTask, User
    from app.services.notification import sms_service

    ch = str(channel or "").upper()
    if ch not in ("SMS", "WECHAT"):
        raise AppException("VALIDATION_ERROR", "仅支持 SMS/WECHAT", http_status=422)
    with session() as db:
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == int(campaign_id),
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            raise not_found("发布单不存在")
        if camp.status not in ("PUBLISHED", "PUBLISHING", "PARTIAL_FAILED"):
            raise AppException("DATA_CONFLICT", "仅已发布消息可外发渠道")

        # WECHAT：当前无配置，只落 SKIPPED 任务
        if ch == "WECHAT":
            t = NotificationTask(
                tenant_id=_tid(),
                biz_type="MESSAGE_CAMPAIGN",
                channel="WECHAT",
                template_code="MESSAGE_CAMPAIGN",
                receiver_name=None,
                receiver_phone_masked=None,
                payload_json={"campaignId": int(campaign_id), "title": camp.title},
                status="SKIPPED",
                last_error="WECHAT_NOT_CONFIGURED",
                created_by=_uid(user),
            )
            db.add(t)
            db.commit()
            return {"channel": "WECHAT", "status": "NOT_CONFIGURED", "taskId": str(t.id)}

        # SMS：逐人尝试；无手机号或未开启则 SKIPPED
        from app.models import UnifiedMessage
        msgs = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.campaign_id == camp.id,
            UnifiedMessage.is_deleted.is_(False),
        ).limit(200)).all()
        results = {"SENT": 0, "SKIPPED": 0, "FAILED": 0}
        for m in msgs:
            uid = m.receiver_user_id or m.receiver_id
            phone = None
            name = None
            if uid:
                u = db.get(User, int(uid))
                if u:
                    phone = getattr(u, "phone", None) or getattr(u, "mobile", None)
                    name = u.real_name
            res = sms_service.send_sms(
                _tid(), phone, "MESSAGE_CAMPAIGN",
                {"title": camp.title, "summary": (camp.summary or "")[:40]},
                biz_type="MESSAGE_CAMPAIGN", receiver_name=name)
            results[res.get("status", "FAILED")] = results.get(res.get("status", "FAILED"), 0) + 1
        return {"channel": "SMS", "results": results}


def reconcile_message_stats(user: dict | None = None) -> dict:
    """统计字段与个人消息对账 + outbox/投递积压告警。"""
    from app.models import MessageCampaign, MessageDeliveryJob, MessageEventOutbox, UnifiedMessage

    with session() as db:
        camps = db.scalars(select(MessageCampaign).where(
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
            MessageCampaign.status.in_(("PUBLISHED", "PARTIAL_FAILED", "PUBLISHING")),
        ).limit(200)).all()
        drift = []
        for c in camps:
            real_delivered = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(),
                UnifiedMessage.campaign_id == c.id,
                UnifiedMessage.is_deleted.is_(False),
            )) or 0
            real_read = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(),
                UnifiedMessage.campaign_id == c.id,
                UnifiedMessage.status == "READ",
                UnifiedMessage.is_deleted.is_(False),
            )) or 0
            real_ack = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(),
                UnifiedMessage.campaign_id == c.id,
                UnifiedMessage.ack_at.is_not(None),
                UnifiedMessage.is_deleted.is_(False),
            )) or 0
            if (int(c.delivered_count or 0) != real_delivered
                    or int(c.read_count or 0) != real_read
                    or int(c.ack_count or 0) != real_ack):
                drift.append({
                    "campaignId": str(c.id),
                    "title": c.title,
                    "counters": {
                        "delivered": [c.delivered_count, real_delivered],
                        "read": [c.read_count, real_read],
                        "ack": [c.ack_count, real_ack],
                    },
                })
                # 自愈：回写真实计数
                c.delivered_count = real_delivered
                c.read_count = real_read
                c.ack_count = real_ack
                c.version = int(c.version or 0) + 1

        outbox_pending = db.scalar(select(func.count()).select_from(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.is_deleted.is_(False),
            MessageEventOutbox.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
        )) or 0
        outbox_dead = db.scalar(select(func.count()).select_from(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == _tid(),
            MessageEventOutbox.is_deleted.is_(False),
            MessageEventOutbox.status == "DEAD",
        )) or 0
        job_pending = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
            MessageDeliveryJob.tenant_id == _tid(),
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status.in_(("PENDING", "RETRY_WAIT", "PROCESSING")),
        )) or 0
        job_dead = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
            MessageDeliveryJob.tenant_id == _tid(),
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status == "DEAD",
        )) or 0
        if drift:
            db.commit()

        alerts = []
        if outbox_pending >= 100:
            alerts.append({"level": "WARN", "code": "OUTBOX_BACKLOG", "count": outbox_pending})
        if outbox_dead > 0:
            alerts.append({"level": "ERROR", "code": "OUTBOX_DEAD", "count": outbox_dead})
        if job_pending >= 50:
            alerts.append({"level": "WARN", "code": "DELIVERY_JOB_BACKLOG", "count": job_pending})
        if job_dead > 0:
            alerts.append({"level": "ERROR", "code": "DELIVERY_JOB_DEAD", "count": job_dead})

        return {
            "checkedAt": _iso(datetime.utcnow()),
            "driftFixed": len(drift),
            "drifts": drift[:50],
            "backlog": {
                "outboxPending": outbox_pending,
                "outboxDead": outbox_dead,
                "deliveryPending": job_pending,
                "deliveryDead": job_dead,
            },
            "alerts": alerts,
        }
