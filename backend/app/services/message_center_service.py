"""消息中心统一领域服务（收件面优先；发布面逐步补齐）。

原则（设计文档不可妥协决策）：
1. 唯一接收人主键是 user_id（receiver_user_id）；历史 receiver_id 仅兼容读取。
2. 已读 ≠ 确认 ≠ 业务办理。
3. 详情查询本身不自动已读。
4. read-all 只更新当前筛选快照内、本人可见的未读记录，绝不代替确认。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, case, func, or_, select

from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.services.db_service import _iso, _tid, session


def _uid(user: dict | None) -> int:
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user)


def _is_student(user: dict | None) -> bool:
    return str((user or {}).get("userType") or "").strip().upper() == "STUDENT"


def _require_inbox_perm(user: dict, code: str) -> None:
    """管理端/教师端校验 workbench.message.*；学生端走本人收件，不套工作台权限码。"""
    if _is_student(user):
        return
    enforce_permission(user, code)


def _utc_now() -> datetime:
    return datetime.utcnow()


def _context_key(user: dict | None) -> str:
    """当前激活身份键；无则只看 GLOBAL。"""
    ctx = str((user or {}).get("activeContextId") or "").strip()
    return ctx or "GLOBAL"


def _visibility(user: dict):
    """本人可见：新字段 receiver_user_id，或兼容旧 receiver_id==user_id。

    身份边界：GLOBAL 永远可见；带 context 的消息仅当激活身份匹配时可见。
    无法解析 uid 时 fail-closed。
    """
    from app.models import UnifiedMessage
    uid = _uid(user)
    if not uid:
        return None
    ctx = _context_key(user)
    new_path = and_(
        UnifiedMessage.receiver_user_id == uid,
        or_(
            UnifiedMessage.receiver_context_key == "GLOBAL",
            UnifiedMessage.receiver_context_key == ctx,
        ),
    )
    # 历史行：receiver_user_id 为空时，仅当 receiver_id 恰好等于 user_id 才可见（禁止猜测学籍/教师档案）
    legacy_path = and_(
        UnifiedMessage.receiver_user_id.is_(None),
        UnifiedMessage.receiver_id == uid,
    )
    return or_(new_path, legacy_path)


def _category_of(row) -> str:
    if row.category:
        return row.category
    mt = (row.message_type or "").upper()
    if mt in ("EMERGENCY",):
        return "EMERGENCY"
    if mt in ("ANNOUNCEMENT", "NOTICE"):
        return "ANNOUNCEMENT"
    if mt in ("TODO_NOTICE", "TODO", "REMINDER"):
        return "TODO"
    if mt in ("BUSINESS", "BIZ"):
        return "BUSINESS"
    return "SYSTEM"


def _priority_of(row) -> str:
    if row.priority:
        return row.priority
    if _category_of(row) == "EMERGENCY" or (row.message_type or "").upper() == "EMERGENCY":
        return "EMERGENCY"
    return "NORMAL"


def _display_title(row) -> str:
    return row.rendered_title or row.title


def _display_content(row) -> str:
    if row.rendered_content_plain:
        return row.rendered_content_plain
    return row.content or ""


def _msg_dict(row, *, detail: bool = False) -> dict:
    title = _display_title(row)
    content = _display_content(row)
    summary = (content or "")[:120]
    cat = _category_of(row)
    pri = _priority_of(row)
    need_ack = bool(getattr(row, "require_ack", False))
    ack_at = getattr(row, "ack_at", None)
    withdrawn = getattr(row, "withdrawn_at", None)
    expired = False
    exp = getattr(row, "expire_at", None)
    if exp and exp < _utc_now():
        expired = True
    d = {
        "messageId": str(row.id),
        "campaignId": str(row.campaign_id) if row.campaign_id else None,
        "category": cat,
        "msgType": row.message_type or cat,
        "priority": pri,
        "title": title,
        "summary": summary,
        "readStatus": row.status,
        "requireAck": need_ack,
        "acked": bool(ack_at),
        "ackAt": _iso(ack_at) if ack_at else None,
        "readAt": _iso(row.read_at) if row.read_at else None,
        "deliveredAt": _iso(getattr(row, "delivered_at", None)) if getattr(row, "delivered_at", None) else None,
        "pinned": bool(getattr(row, "pinned", False)),
        "emergency": pri == "EMERGENCY" or cat == "EMERGENCY",
        "withdrawn": bool(withdrawn),
        "withdrawReason": getattr(row, "withdraw_reason", None) if withdrawn else None,
        "expired": expired,
        "expireAt": _iso(exp) if exp else None,
        "senderOrgName": getattr(row, "sender_org_name_snapshot", None),
        "actionKey": getattr(row, "action_key", None),
        "actionParams": getattr(row, "action_params_json", None),
        "contentVersion": int(getattr(row, "content_version", 1) or 1),
        "createdAt": _iso(row.created_at) if row.created_at else None,
        # 兼容旧工作台/小程序字段
        "actionUrl": None,
    }
    if detail:
        d["content"] = content
        d["contentPlain"] = content
    return d


def _filter_conds(vis, *, category: str | None = None, read_status: str | None = None,
                  priority: str | None = None, pending_ack: bool | None = None) -> list:
    from app.models import UnifiedMessage
    conds = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), vis]
    if read_status:
        conds.append(UnifiedMessage.status == read_status.upper())
    if priority:
        p = priority.upper()
        conds.append(or_(
            UnifiedMessage.priority == p,
            and_(UnifiedMessage.priority.is_(None), UnifiedMessage.message_type == p),
        ))
    if pending_ack is True:
        conds.append(UnifiedMessage.require_ack.is_(True))
        conds.append(UnifiedMessage.ack_at.is_(None))
        conds.append(UnifiedMessage.withdrawn_at.is_(None))
    if category and category.upper() not in ("", "ALL"):
        c = category.upper()
        if c == "EMERGENCY":
            conds.append(or_(
                UnifiedMessage.category == "EMERGENCY",
                UnifiedMessage.priority == "EMERGENCY",
                UnifiedMessage.message_type == "EMERGENCY",
            ))
        elif c == "TODO":
            conds.append(or_(
                UnifiedMessage.category == "TODO",
                UnifiedMessage.message_type.in_(("TODO_NOTICE", "TODO", "REMINDER")),
            ))
        elif c == "ANNOUNCEMENT":
            conds.append(or_(
                UnifiedMessage.category == "ANNOUNCEMENT",
                UnifiedMessage.message_type.in_(("ANNOUNCEMENT", "NOTICE")),
            ))
        elif c == "BUSINESS":
            conds.append(or_(
                UnifiedMessage.category == "BUSINESS",
                UnifiedMessage.message_type.in_(("BUSINESS", "BIZ")),
            ))
        elif c == "SYSTEM":
            conds.append(or_(
                UnifiedMessage.category == "SYSTEM",
                UnifiedMessage.message_type == "SYSTEM",
                and_(UnifiedMessage.category.is_(None), UnifiedMessage.message_type.is_(None)),
            ))
        else:
            conds.append(or_(
                UnifiedMessage.category == c,
                UnifiedMessage.message_type == c,
            ))
    return conds


def _sort_order():
    """紧急未确认 > 置顶 > 时间倒序。"""
    from app.models import UnifiedMessage
    emergency_pending = case(
        (and_(
            or_(
                UnifiedMessage.priority == "EMERGENCY",
                UnifiedMessage.category == "EMERGENCY",
                UnifiedMessage.message_type == "EMERGENCY",
            ),
            UnifiedMessage.require_ack.is_(True),
            UnifiedMessage.ack_at.is_(None),
            UnifiedMessage.withdrawn_at.is_(None),
        ), 0),
        else_=1,
    )
    pinned_ord = case((UnifiedMessage.pinned.is_(True), 0), else_=1)
    return emergency_pending.asc(), pinned_ord.asc(), UnifiedMessage.created_at.desc(), UnifiedMessage.id.desc()


def list_messages(
    user: dict,
    *,
    category: str | None = None,
    read_status: str | None = None,
    priority: str | None = None,
    pending_ack: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.view")
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return [], 0
        conds = _filter_conds(
            vis, category=category, read_status=read_status,
            priority=priority, pending_ack=pending_ack)
        total = db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conds)) or 0
        rows = db.scalars(
            select(UnifiedMessage).where(*conds)
            .order_by(*_sort_order())
            .offset(max(0, (page - 1) * page_size)).limit(page_size)
        ).all()
        return [_msg_dict(r) for r in rows], int(total)


def count_messages(user: dict) -> dict:
    """未读 + 待确认。铃铛与收件箱同口径。"""
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.view")
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return {"unread": 0, "pendingAck": 0}
        base = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False), vis]
        unread = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            *base, UnifiedMessage.status == "UNREAD")) or 0
        pending_ack = db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            *base,
            UnifiedMessage.require_ack.is_(True),
            UnifiedMessage.ack_at.is_(None),
            UnifiedMessage.withdrawn_at.is_(None),
        )) or 0
        return {"unread": int(unread), "pendingAck": int(pending_ack)}


def category_counts(user: dict) -> dict:
    """左侧分类导航计数（全部/紧急/公告… + 未读/已读）。"""
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.view")
    keys = ["ALL", "EMERGENCY", "ANNOUNCEMENT", "BUSINESS", "TODO", "SYSTEM"]
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return {k: 0 for k in keys} | {"UNREAD": 0, "READ": 0}
        out: dict[str, int] = {}
        for k in keys:
            conds = _filter_conds(vis, category=None if k == "ALL" else k)
            out[k] = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conds)) or 0)
        out["UNREAD"] = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            *_filter_conds(vis, read_status="UNREAD"))) or 0)
        out["READ"] = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            *_filter_conds(vis, read_status="READ"))) or 0)
        return out


def get_message(user: dict, message_id: str) -> dict | None:
    """详情：严格本人；不自动已读。"""
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.view")
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return None
        try:
            mid = int(message_id)
        except (TypeError, ValueError):
            return None
        row = db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id == mid,
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.is_deleted.is_(False),
            vis,
        ))
        if not row:
            return None
        return _msg_dict(row, detail=True)


def read_message(user: dict, message_id: str) -> dict | None:
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.read")
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return None
        try:
            mid = int(message_id)
        except (TypeError, ValueError):
            return None
        row = db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id == mid,
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.is_deleted.is_(False),
            vis,
        ))
        if not row:
            return None
        if row.status != "READ":
            row.status = "READ"
            row.read_at = _utc_now()
            row.version = int(row.version or 0) + 1
            db.commit()
        return {"messageId": str(row.id), "readStatus": "READ", "readAt": _iso(row.read_at)}


def read_all(
    user: dict,
    *,
    category: str | None = None,
    priority: str | None = None,
) -> dict:
    """按当前筛选批量已读；不确认；不含调用开始后新到达的消息。"""
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.readAll")
    cutoff = _utc_now()
    # 允许小幅时钟偏差（DB now / 应用 now），避免误伤「请求前已写入」的消息
    skew = timedelta(seconds=2)
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            return {"affectedCount": 0, "updatedAt": _iso(cutoff)}
        conds = _filter_conds(vis, category=category, read_status="UNREAD", priority=priority)
        conds.append(UnifiedMessage.created_at <= cutoff + skew)
        rows = db.scalars(select(UnifiedMessage).where(*conds)).all()
        n = 0
        for row in rows:
            row.status = "READ"
            row.read_at = cutoff
            row.version = int(row.version or 0) + 1
            n += 1
        if n:
            db.commit()
        return {"affectedCount": n, "updatedAt": _iso(cutoff)}


def ack_message(user: dict, message_id: str) -> dict:
    """本人确认回执；不等于业务办理完成。"""
    from app.models import UnifiedMessage
    _require_inbox_perm(user, "workbench.message.ack")
    with session() as db:
        vis = _visibility(user)
        if vis is None:
            raise not_found("消息不存在")
        try:
            mid = int(message_id)
        except (TypeError, ValueError):
            raise not_found("消息不存在")
        row = db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id == mid,
            UnifiedMessage.tenant_id == _tid(),
            UnifiedMessage.is_deleted.is_(False),
            vis,
        ))
        if not row:
            raise not_found("消息不存在")
        if getattr(row, "withdrawn_at", None):
            raise AppException("DATA_CONFLICT", "消息已撤回，无法确认",
                               details={"reason": "MESSAGE_WITHDRAWN"})
        if not bool(getattr(row, "require_ack", False)):
            raise AppException("VALIDATION_ERROR", "该消息无需确认回执",
                               details={"reason": "ACK_NOT_REQUIRED"}, http_status=422)
        now = _utc_now()
        if not row.ack_at:
            row.ack_at = now
            if row.status != "READ":
                row.status = "READ"
                row.read_at = now
            row.version = int(row.version or 0) + 1
            db.commit()
        return {
            "messageId": str(row.id),
            "acked": True,
            "ackAt": _iso(row.ack_at),
            "readStatus": row.status,
        }


# ── 兼容适配：供 workbench_todo_service / 旧端点调用 ──

def list_messages_compat(user: dict, read_status: Optional[str] = None,
                         page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    return list_messages(user, read_status=read_status, page=page, page_size=page_size)


def count_messages_compat(user: dict) -> dict:
    return count_messages(user)


def read_message_compat(user: dict, message_id: str) -> dict | None:
    return read_message(user, message_id)
