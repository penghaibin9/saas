"""消息中心：统计 / 模板只读 / 渠道设置状态。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.core.exceptions import no_permission
from app.core.permissions import has_permission
from app.services.db_service import _iso, _tid, session


def _can_stats(user: dict) -> bool:
    return any(has_permission(user, c) for c in (
        "workbench.message.statistics.view",
        "workbench.message.publish",
        "workbench.message.class.publish",
        "workbench.message.college.publish",
        "workbench.message.schoolAll.publish",
        "*",
    ))


def _uid(user: dict | None) -> int:
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user)


def statistics_summary(user: dict, *, days: int = 30) -> dict:
    """发布与回执汇总（权限范围内）。口径：分子=已发生计数，分母=发布单 recipient_count 合计。"""
    if not _can_stats(user):
        raise no_permission("无消息统计权限")
    from app.models import MessageCampaign

    days = max(1, min(365, int(days or 30)))
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # 粗略：用 created_at 近 N 天；若无 timezone 以 UTC 日切
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    school_view = (
        has_permission(user, "workbench.message.statistics.view")
        or has_permission(user, "workbench.message.schoolAll.publish")
        or has_permission(user, "*")
    )
    with session() as db:
        conds = [
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
            MessageCampaign.created_at >= since,
        ]
        if not school_view:
            conds.append(MessageCampaign.sender_user_id == _uid(user))

        rows = db.scalars(select(MessageCampaign).where(*conds)).all()
        campaign_count = len(rows)
        recipient = sum(int(r.recipient_count or 0) for r in rows)
        delivered = sum(int(r.delivered_count or 0) for r in rows)
        read = sum(int(r.read_count or 0) for r in rows)
        ack = sum(int(r.ack_count or 0) for r in rows)
        failure = sum(int(r.failure_count or 0) for r in rows)

        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            cat = r.category or "ANNOUNCEMENT"
            by_category[cat] = by_category.get(cat, 0) + 1

        def rate(n, d):
            return round((n / d) * 100, 1) if d else 0.0

        return {
            "days": days,
            "updatedAt": _iso(datetime.utcnow()),
            "metrics": {
                "campaignCount": campaign_count,
                "recipientCount": recipient,
                "deliveredCount": delivered,
                "readCount": read,
                "ackCount": ack,
                "failureCount": failure,
                "deliveryRate": rate(delivered, recipient),
                "readRate": rate(read, max(delivered, 1) if delivered else 0) if delivered else 0.0,
                "ackRate": rate(ack, recipient),
            },
            "denominatorNote": (
                "recipientCount=各发布单受理时受众快照人数合计；"
                "delivered/read/ack 为发布单累计字段（投递后增量更新）。"
            ),
            "byStatus": [{"status": k, "count": v} for k, v in sorted(by_status.items())],
            "byCategory": [{"category": k, "count": v} for k, v in sorted(by_category.items())],
            "channels": [
                {"channel": "IN_APP", "status": "READY", "label": "站内消息"},
                {"channel": "SMS", "status": "NOT_CONFIGURED", "label": "短信（未配置）"},
                {"channel": "WECHAT", "status": "NOT_CONFIGURED", "label": "微信订阅（未配置）"},
            ],
        }


def list_message_templates(user: dict, *, keyword: Optional[str] = None,
                           page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    """复用 t_notification_template；只读列表 + 启停态。"""
    if not _can_stats(user) and not has_permission(user, "workbench.message.publish"):
        # 有发布权也可看模板
        if not any(has_permission(user, c) for c in (
            "workbench.message.class.publish", "workbench.message.college.publish",
            "workbench.message.schoolStudent.publish", "workbench.message.schoolAll.publish",
            "*",
        )):
            raise no_permission("无模板查看权限")
    from app.models import NotificationTemplate

    kw = (keyword or "").strip().lower()
    with session() as db:
        conds = [
            NotificationTemplate.tenant_id == _tid(),
            NotificationTemplate.is_deleted.is_(False),
        ]
        rows = db.scalars(
            select(NotificationTemplate).where(*conds)
            .order_by(NotificationTemplate.template_code.asc(), NotificationTemplate.channel.asc())
        ).all()
        items = []
        for r in rows:
            code = r.template_code or ""
            title = r.title or code
            if kw and kw not in code.lower() and kw not in (title or "").lower() and kw not in (r.event_code or "").lower():
                continue
            items.append({
                "templateId": str(r.id),
                "templateCode": code,
                "eventCode": r.event_code,
                "channel": r.channel,
                "title": title,
                "content": r.content,
                "enabled": bool(r.enabled),
                "version": r.template_version,
                "variables": r.variables_json or [],
                "lockedFields": r.locked_fields_json or [],
                "kind": "SYSTEM" if (r.event_code or code.startswith("LEAVE") or code.startswith("SYS")) else "HUMAN",
                "previewSample": _safe_preview(r.content or ""),
            })
        total = len(items)
        start = max(0, (page - 1) * page_size)
        return items[start:start + page_size], total


def _safe_preview(content: str) -> str:
    """示例预览：用固定占位替换变量，不暴露真实学生。"""
    sample = (content or "")[:500]
    for k, v in (
        ("{name}", "同学甲"), ("{studentName}", "同学甲"), ("{title}", "示例标题"),
        ("{days}", "2"), ("{endAt}", "2026-07-30 18:00"),
    ):
        sample = sample.replace(k, v)
    return sample


def channel_settings(user: dict) -> dict:
    """个人外部渠道偏好 + 渠道配置态。站内消息不可关。"""
    from app.services import message_governance_service as gov
    from app.services import notification_preference_service as pref

    ut = str((user or {}).get("userType") or "").upper()
    cats = pref.TEACHER_CATEGORIES if ut != "STUDENT" else pref.STUDENT_CATEGORIES
    prefs = pref.get_preferences(user, cats)
    return {
        "note": "以下仅控制外部打扰；站内正式消息、紧急与强制送达不可关闭。",
        "preferences": prefs.get("items") or [],
        "channels": [
            {"key": "IN_APP", "label": "站内消息", "status": "FORCE_ON",
             "hint": "正式留存，不可关闭"},
            {"key": "MINIAPP_POPUP", "label": "小程序弹出提醒", "status": "READY",
             "hint": "受分类偏好控制；紧急消息仍会提示"},
            {"key": "SMS", "label": "短信", "status": "NOT_CONFIGURED",
             "hint": "未配置短信服务商，不会假发送"},
            {"key": "WECHAT", "label": "微信订阅消息", "status": "NOT_CONFIGURED",
             "hint": "未配置微信模板，不会假发送"},
        ],
        "quietHours": {
            "enabled": True,
            "start": "22:00",
            "end": "07:00",
            "hint": "普通消息落在静默时段将自动顺延；紧急消息可绕过并记审计备注",
            "inQuietNow": gov.is_in_quiet_hours(),
        },
        "rateLimit": {
            "maxPerHour": 20,
            "hint": "同发布人 60 分钟内最多受理 20 次发布",
        },
    }


def set_channel_preference(user: dict, key: str, enabled: bool) -> dict:
    from app.services import notification_preference_service as pref
    ut = str((user or {}).get("userType") or "").upper()
    cats = pref.TEACHER_CATEGORIES if ut != "STUDENT" else pref.STUDENT_CATEGORIES
    valid = {c["key"] for c in cats}
    if key not in valid:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "未知偏好分类", http_status=422)
    return pref.set_preference(user, key, enabled)
