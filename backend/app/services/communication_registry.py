"""SYS-15 统一消息、待办与通知治理：注册表 + 只读治理视图。

第一阶段只做"代码/YAML 注册表 + adapter"，不新建统一大表：
- 事件去重权威在 app.services.message_event_outbox_service.emit_message_event()
  （t_message_event_outbox.dedup_key 唯一约束）；
- 待办去重权威在 t_unified_todo.uk_todo_dedup 唯一约束
  （app.modules.graduation.services.graduation_todo_helper.todo_upsert 是已生产验证的实现范式）；
- 本模块只读这些既有表，叠加"谁负责、有没有登记"的治理判断，不改写业务数据。

registry.yaml 路径固定在 docs/architecture/communication-capability-registry.yaml，
登记的是"治理元数据"（ownerModule/slaHours/deepLinkPattern），不是事件码是否合法——
事件码合法性仍由 message_event_outbox_service._EVENT_TEMPLATES 说了算。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select

from app.models import MessageEventOutbox, NotificationLog, NotificationTemplate, UnifiedTodo
from app.services.db_service import _tid

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "docs" / "architecture" / \
    "communication-capability-registry.yaml"

_cache: dict[str, Any] = {}


def _load_registry() -> dict[str, Any]:
    """读取 YAML 注册表；文件不存在时返回空登记（治理面板整体标未登记，而不是报错）。"""
    mtime = REGISTRY_PATH.stat().st_mtime if REGISTRY_PATH.exists() else None
    if _cache.get("_mtime") == mtime and "_mtime" in _cache:
        return _cache["data"]
    if not REGISTRY_PATH.exists():
        data: dict[str, Any] = {"version": 0, "events": [], "todoTypes": [], "channels": []}
    else:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    _cache["_mtime"] = mtime
    _cache["data"] = data
    return data


def registered_event_codes() -> set[str]:
    return {str(e.get("eventCode", "")).strip().upper() for e in _load_registry().get("events", [])}


def registered_todo_types() -> dict[str, dict]:
    return {str(t.get("todoType", "")).strip(): t for t in _load_registry().get("todoTypes", [])}


def registered_channels() -> dict[str, dict]:
    return {str(c.get("channel", "")).strip().upper(): c for c in _load_registry().get("channels", [])}


def list_registry() -> dict[str, Any]:
    data = _load_registry()
    return {
        "events": data.get("events", []),
        "todoTypes": data.get("todoTypes", []),
        "channels": data.get("channels", []),
        "version": data.get("version"),
    }


def validate_registry() -> dict[str, Any]:
    """交叉校验：注册表登记的事件码是否在真正的事件模板里存在（真实来源永远是 _EVENT_TEMPLATES）。"""
    from app.services.message_event_outbox_service import _EVENT_TEMPLATES

    real_codes = set(_EVENT_TEMPLATES.keys())
    reg_codes = registered_event_codes()
    return {
        "registeredButUnknownToCode": sorted(reg_codes - real_codes),
        "knownToCodeButUnregistered": sorted(real_codes - reg_codes),
        "registryVersion": _load_registry().get("version"),
    }


def governance_overview(db=None) -> dict[str, Any]:
    """治理首屏：投递失败、渠道健康、重复模板、待办积压/逾期、无责任人异常队列。全部读真实表。

    不传 db 时自己开关会话（供路由直接调用）；传入 db 时复用调用方会话（供测试/编排复用）。"""
    if db is None:
        from app.db.session import get_sessionmaker
        session = get_sessionmaker()()
        try:
            return governance_overview(session)
        finally:
            session.close()

    tid = _tid()
    now = datetime.utcnow()

    dead_outbox = int(db.scalar(select(func.count()).select_from(MessageEventOutbox).where(
        MessageEventOutbox.tenant_id == tid, MessageEventOutbox.is_deleted.is_(False),
        MessageEventOutbox.status == "DEAD")) or 0)
    recent_since = now - timedelta(days=7)
    fail_logs = int(db.scalar(select(func.count()).select_from(NotificationLog).where(
        NotificationLog.tenant_id == tid, NotificationLog.result == "FAIL",
        NotificationLog.sent_at >= recent_since)) or 0)

    reg_channels = registered_channels()
    channel_health = []
    for code, meta in reg_channels.items():
        enabled_count = int(db.scalar(select(func.count()).select_from(NotificationTemplate).where(
            NotificationTemplate.tenant_id == tid, NotificationTemplate.is_deleted.is_(False),
            NotificationTemplate.channel == code, NotificationTemplate.enabled.is_(True))) or 0)
        channel_health.append({
            "channel": code, "provider": meta.get("provider"),
            "enabledTemplateCount": enabled_count,
            "healthy": enabled_count > 0,
        })

    dup_rows = db.execute(select(
        NotificationTemplate.event_code, NotificationTemplate.channel, func.count().label("cnt"),
    ).where(
        NotificationTemplate.tenant_id == tid, NotificationTemplate.is_deleted.is_(False),
        NotificationTemplate.event_code.is_not(None),
    ).group_by(NotificationTemplate.event_code, NotificationTemplate.channel)
     .having(func.count() > 1)).all()
    duplicate_templates = [
        {"eventCode": r[0], "channel": r[1], "templateCount": int(r[2])} for r in dup_rows
    ]

    backlog = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tid, UnifiedTodo.is_deleted.is_(False),
        UnifiedTodo.status == "PENDING")) or 0)
    overdue = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tid, UnifiedTodo.is_deleted.is_(False),
        UnifiedTodo.status == "PENDING", UnifiedTodo.due_at.is_not(None),
        UnifiedTodo.due_at < now)) or 0)

    reg_todo_types = set(registered_todo_types().keys())
    live_types = [row[0] for row in db.execute(select(UnifiedTodo.todo_type).where(
        UnifiedTodo.tenant_id == tid, UnifiedTodo.is_deleted.is_(False),
    ).distinct()).all()]
    unowned_todo_types = sorted(t for t in live_types if t not in reg_todo_types)

    validation = validate_registry()

    return {
        "deliveryFailures": {"deadOutbox": dead_outbox, "notificationFailLast7d": fail_logs},
        "channelHealth": channel_health,
        "duplicateTemplates": duplicate_templates,
        "todoBacklog": backlog,
        "todoOverdue": overdue,
        "exceptionQueue": {
            "unownedTodoTypes": unowned_todo_types,
            "unregisteredEventCodesInCode": validation["knownToCodeButUnregistered"],
        },
        "registry": validation,
    }
