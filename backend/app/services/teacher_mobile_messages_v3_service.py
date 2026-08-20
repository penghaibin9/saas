"""Teacher Miniapp V3 T9 message inbox: signed eventAt/id keyset pagination.

The old teacher miniapp pulled every message group and then used listPaging in memory. This module makes UnifiedMessage the server-side inbox projection and keeps the page bounded at 20/max50. Cursor semantics intentionally use created_at as eventAt: it is immutable for the recipient row and already participates in the receiver/context index, while delivered_at is nullable and can change during delivery reconciliation.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, not_, or_, select

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.permissions import enforce_permission
from app.core.security import MOBILE_STAFF_USER_TYPES
from app.services import message_center_service as message_center
from app.services import mobile_action_service as mobile_actions
from app.services.db_service import _iso, _tid, session
from app.services.message_identity import resolve_message_user_id

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 2048
_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 50
_ALLOWED_TABS = ("system", "dynamic", "risk", "urge")
_TAB_LABELS = {"system": "系统通知", "dynamic": "学生动态", "risk": "风险预警", "urge": "催办提醒"}


def _require_teacher(user: dict | None, *, permission: str = "workbench.message.view") -> dict:
    """Teacher identity + canonical message permission gate.

    ``require_staff`` at the HTTP layer is only an identity gate. Custom school roles can be staff
    without inbox permission, so T9 must not turn the new high-performance endpoint into a bypass
    around the canonical ``workbench.message.*`` authority.
    """
    u = user or {}
    if not u.get("userId") or str(u.get("userType") or "").strip().upper() not in MOBILE_STAFF_USER_TYPES:
        raise AppException("NO_PERMISSION", "该接口仅学校教职工移动端可用", http_status=403)
    enforce_permission(u, permission)
    return u


def _validation_error(message: str) -> AppException:
    return AppException("VALIDATION_ERROR", message, details={"reason": "INVALID_MESSAGE_CURSOR"})


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(token: str) -> bytes:
    return base64.urlsafe_b64decode((token + "=" * (-len(token) % 4)).encode("ascii"))


def _cursor_signature(raw: bytes) -> bytes:
    secret = str(settings.jwt_secret or "").encode("utf-8")
    if not secret:
        raise AppException("SERVER_ERROR", "游标签名密钥未配置", details={"reason": "CURSOR_SIGNING_KEY_MISSING"})
    return hmac.new(secret, raw, hashlib.sha256).digest()


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64encode(raw)}.{_b64encode(_cursor_signature(raw))}"


def _parse_event_at(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor eventAt 不合法") from exc
    if parsed.tzinfo is not None:
        raise _validation_error("cursor eventAt 时区格式不合法")
    return parsed


def _filter_hash(user: dict, *, tab: str, q: str) -> str:
    payload = {
        "client": "teacherMini", "tenantId": int(_tid() or 0),
        "userId": int(resolve_message_user_id(user) or 0),
        "context": str(user.get("activeContextId") or "GLOBAL"),
        "tab": tab, "q": q, "sort": "eventAt:desc,id:desc",
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _decode_cursor(cursor: str, *, expected_filter_hash: str) -> dict[str, Any]:
    token = str(cursor or "").strip()
    if not token or len(token) > _MAX_CURSOR_LENGTH or token.count(".") != 1:
        raise _validation_error("cursor 为空、过长或格式不合法")
    try:
        body_token, signature_token = token.split(".", 1)
        raw = _b64decode(body_token)
        if not hmac.compare_digest(_b64decode(signature_token), _cursor_signature(raw)):
            raise _validation_error("cursor 签名校验失败")
        payload = json.loads(raw.decode("utf-8"))
    except AppException:
        raise
    except (ValueError, TypeError, binascii.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise _validation_error("cursor 无法解析") from exc
    if not isinstance(payload, dict) or int(payload.get("v") or 0) != _CURSOR_VERSION:
        raise _validation_error("cursor 版本不兼容")
    if str(payload.get("filterHash") or "") != expected_filter_hash:
        raise _validation_error("cursor 与当前筛选条件不一致")
    try:
        row_id = int(payload.get("id") or 0)
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor id 不合法") from exc
    if row_id <= 0:
        raise _validation_error("cursor id 不合法")
    payload["id"] = row_id
    payload["eventAt"] = _parse_event_at(payload.get("eventAt"))
    return payload


def _normalize_tab(tab: str | None, *, allow_all: bool = False) -> str:
    value = str(tab or "system").strip().lower()
    if allow_all and value == "all":
        return value
    if value not in _ALLOWED_TABS:
        raise AppException("VALIDATION_ERROR", "消息分类不合法", details={"tab": value})
    return value


def _normalize_query(q: str | None) -> str:
    value = str(q or "").strip()
    if len(value) > 40:
        raise AppException("VALIDATION_ERROR", "搜索关键词过长")
    if value and len(value) < 2:
        raise AppException("VALIDATION_ERROR", "搜索关键词至少 2 个字符")
    return value


def _tab_predicates(UnifiedMessage):
    category = func.upper(func.coalesce(UnifiedMessage.category, ""))
    msg_type = func.upper(func.coalesce(UnifiedMessage.message_type, ""))
    priority = func.upper(func.coalesce(UnifiedMessage.priority, ""))
    risk = or_(category == "EMERGENCY", priority == "EMERGENCY", msg_type == "EMERGENCY")
    urge_raw = or_(category == "TODO", msg_type.in_(("TODO_NOTICE", "TODO", "REMINDER")))
    dynamic_raw = or_(category == "BUSINESS", msg_type.in_(("BUSINESS", "BIZ")))
    return {
        "system": and_(not_(risk), not_(urge_raw), not_(dynamic_raw)),
        "dynamic": and_(not_(risk), not_(urge_raw), dynamic_raw),
        "risk": risk,
        "urge": and_(not_(risk), urge_raw),
    }


def _classify_row(row) -> str:
    category = str(getattr(row, "category", None) or "").upper()
    msg_type = str(getattr(row, "message_type", None) or "").upper()
    priority = str(getattr(row, "priority", None) or "").upper()
    if "EMERGENCY" in (category, msg_type, priority):
        return "risk"
    if category == "TODO" or msg_type in ("TODO_NOTICE", "TODO", "REMINDER"):
        return "urge"
    if category == "BUSINESS" or msg_type in ("BUSINESS", "BIZ"):
        return "dynamic"
    return "system"


def _prefix_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _base_conditions(user: dict, UnifiedMessage, *, tab: str, q: str) -> list:
    vis = message_center.visibility_condition(user)
    if vis is None:
        return []
    conds = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), UnifiedMessage.created_at.is_not(None), vis]
    if tab != "all":
        conds.append(_tab_predicates(UnifiedMessage)[tab])
    if q:
        pattern = _prefix_pattern(q)
        conds.append(or_(UnifiedMessage.title.ilike(pattern, escape="\\"), UnifiedMessage.rendered_title.ilike(pattern, escape="\\")))
    return conds


def _message_action(row) -> dict | None:
    key = str(getattr(row, "action_key", None) or "").strip()
    params = dict(getattr(row, "action_params_json", None) or {})
    if not key:
        key, params = "message.detail", {"messageId": str(row.id)}
    return mobile_actions.build_message_action(key, params, client=mobile_actions.CLIENT_TEACHER_MINI, withdrawn=bool(getattr(row, "withdrawn_at", None)))


def _detail_action(row) -> dict | None:
    return mobile_actions.build_message_action("message.detail", {"messageId": str(row.id)}, client=mobile_actions.CLIENT_TEACHER_MINI, withdrawn=bool(getattr(row, "withdrawn_at", None)))


def _item(row) -> dict:
    category = _classify_row(row)
    event_at = row.created_at
    display_at = getattr(row, "delivered_at", None) or event_at
    priority = str(getattr(row, "priority", None) or "").upper()
    return {
        "id": str(row.id), "messageId": str(row.id), "kind": "UNIFIED_MESSAGE", "tab": category,
        "title": getattr(row, "rendered_title", None) or row.title,
        "module": getattr(row, "sender_org_name_snapshot", None) or getattr(row, "source_module", None) or _TAB_LABELS[category],
        "level": "high" if category == "risk" or priority in ("IMPORTANT", "EMERGENCY") else "normal",
        "read": str(getattr(row, "status", "") or "").upper() == "READ", "status": getattr(row, "status", None),
        "eventAt": _iso(event_at), "time": _iso(display_at),
        "requireAck": bool(getattr(row, "require_ack", False)), "acked": bool(getattr(row, "ack_at", None)),
        "withdrawn": bool(getattr(row, "withdrawn_at", None)),
        "action": _message_action(row), "detailAction": _detail_action(row),
    }


def list_messages(user: dict, *, tab: str = "system", cursor: str | None = None, page_size: int = _PAGE_SIZE_DEFAULT, q: str | None = None) -> dict[str, Any]:
    from app.models import UnifiedMessage
    u = _require_teacher(user)
    normalized_tab = _normalize_tab(tab, allow_all=True)
    query = _normalize_query(q)
    size = max(1, min(_PAGE_SIZE_MAX, int(page_size or _PAGE_SIZE_DEFAULT)))
    filter_hash = _filter_hash(u, tab=normalized_tab, q=query)
    cursor_payload = _decode_cursor(str(cursor), expected_filter_hash=filter_hash) if str(cursor or "").strip() else None
    with session() as db:
        conds = _base_conditions(u, UnifiedMessage, tab=normalized_tab, q=query)
        if not conds:
            return {"items": [], "pageSize": size, "nextCursor": None, "hasMore": False, "filterHash": filter_hash, "sort": "eventAt:desc,id:desc"}
        if cursor_payload is not None:
            event_at, row_id = cursor_payload["eventAt"], int(cursor_payload["id"])
            conds.append(or_(UnifiedMessage.created_at < event_at, and_(UnifiedMessage.created_at == event_at, UnifiedMessage.id < row_id)))
        rows = db.scalars(select(UnifiedMessage).where(*conds).order_by(UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc()).limit(size + 1)).all()
        has_more, page_rows = len(rows) > size, rows[:size]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor({"v": _CURSOR_VERSION, "filterHash": filter_hash, "eventAt": last.created_at.isoformat(timespec="microseconds"), "id": int(last.id)})
        return {"items": [_item(row) for row in page_rows], "pageSize": size, "nextCursor": next_cursor, "hasMore": has_more, "filterHash": filter_hash, "sort": "eventAt:desc,id:desc"}


def unread_badges(user: dict) -> dict[str, Any]:
    from app.models import UnifiedMessage
    u = _require_teacher(user)
    vis = message_center.visibility_condition(u)
    zero = {key: 0 for key in _ALLOWED_TABS}
    if vis is None:
        return {"badges": zero, "total": 0}
    predicates = _tab_predicates(UnifiedMessage)
    unread = and_(UnifiedMessage.status == "UNREAD", UnifiedMessage.withdrawn_at.is_(None))
    columns = [func.sum(case((and_(unread, predicates[key]), 1), else_=0)).label(key) for key in _ALLOWED_TABS]
    with session() as db:
        row = db.execute(select(*columns).where(UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), vis)).one()
    badges = {key: int(getattr(row, key) or 0) for key in _ALLOWED_TABS}
    return {"badges": badges, "total": sum(badges.values())}


def get_message(user: dict, message_id: str) -> dict:
    from app.models import UnifiedMessage
    u = _require_teacher(user)
    try:
        mid = int(message_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "messageId 不合法") from exc
    vis = message_center.visibility_condition(u)
    if vis is None:
        raise AppException("NOT_FOUND", "消息不存在或无权访问", http_status=404)
    with session() as db:
        row = db.scalar(select(UnifiedMessage).where(UnifiedMessage.id == mid, UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), vis))
        if not row:
            raise AppException("NOT_FOUND", "消息不存在或无权访问", http_status=404)
        base, item = message_center._msg_dict(row, detail=True), _item(row)
        return {**item, "title": base.get("title") or item["title"], "content": base.get("content") or "", "summary": base.get("summary") or "", "emergency": bool(base.get("emergency")), "receipt": bool(base.get("requireAck")) and not bool(base.get("acked")), "requireAck": bool(base.get("requireAck")), "acked": bool(base.get("acked")), "ackAt": base.get("ackAt"), "readAt": base.get("readAt"), "expireAt": base.get("expireAt"), "expired": bool(base.get("expired")), "withdrawReason": base.get("withdrawReason")}


def ack_message(user: dict, message_id: str) -> dict:
    _require_teacher(user, permission="workbench.message.ack")
    return message_center.ack_message(user, message_id)
