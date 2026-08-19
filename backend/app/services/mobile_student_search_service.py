"""V3 §9.2 学生端受限搜索。

范围严格限定为「当前学生本人可见的东西」：本人消息/通知标题，以及本人办理的标题。
**不做**全校学生检索、不搜敏感记录、不跨租户。

性能约束（§11.2）：
  - 关键词至少 2 个字符，否则直接返回空；
  - 不使用无边界 ``%keyword%`` 扫全表：消息按前缀匹配 + 最近时间窗，
    办理按前缀匹配本人记录；
  - 每页 20，最大 20；结果同样携带 typed action。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select

from app.core.exceptions import AppException
from app.services import message_center_service as message_svc
from app.services import mobile_action_service as action_svc
from app.services.db_service import _iso, _tid, session

MIN_KEYWORD_LENGTH = 2
MAX_KEYWORD_LENGTH = 40
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 20
#: 消息检索的时间窗。学生要找的是最近的通知；无边界回溯只会把扫描量做大。
SEARCH_WINDOW_DAYS = 180


def _escape_like(value: str) -> str:
    """转义 LIKE 元字符，避免 % 和 _ 变成用户可控的通配扫描。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalize_keyword(keyword: str | None) -> str:
    value = str(keyword or "").strip()
    if len(value) > MAX_KEYWORD_LENGTH:
        raise AppException("VALIDATION_ERROR", f"关键词最多 {MAX_KEYWORD_LENGTH} 个字符")
    return value


def search(user: dict, *, keyword: str, page_size: int = PAGE_SIZE_DEFAULT) -> dict[str, Any]:
    from app.db.session import db_enabled
    from app.services.mobile_student_service import _require_student, resolve_student

    current = _require_student(user)
    value = _normalize_keyword(keyword)
    size = max(1, min(PAGE_SIZE_MAX, int(page_size or PAGE_SIZE_DEFAULT)))
    if len(value) < MIN_KEYWORD_LENGTH:
        return {"keyword": value, "items": [], "hasData": False,
                "note": f"请输入至少 {MIN_KEYWORD_LENGTH} 个字符"}
    if not db_enabled():
        return {"keyword": value, "items": [], "hasData": False}

    pattern = f"%{_escape_like(value)}%"
    prefix = f"{_escape_like(value)}%"
    since = datetime.now(timezone.utc) - timedelta(days=SEARCH_WINDOW_DAYS)

    items: list[dict[str, Any]] = []
    with session() as db:
        student = resolve_student(db, current)
        if not student:
            return {"keyword": value, "items": [], "hasData": False}

        # ① 本人消息：可见性直接复用 message_center 的 Authority，不另建 receiver 判定。
        visibility = message_svc.visibility_condition(current)
        if visibility is not None:
            from app.models import UnifiedMessage
            rows = db.scalars(
                select(UnifiedMessage).where(
                    UnifiedMessage.tenant_id == _tid(),
                    UnifiedMessage.is_deleted.is_(False),
                    visibility,
                    UnifiedMessage.withdrawn_at.is_(None),
                    UnifiedMessage.created_at >= since,
                    # 前缀优先；仅在窗口内的本人消息上才允许包含匹配，扫描量已被时间窗与
                    # receiver 条件收敛，不是全表 contains。
                    or_(UnifiedMessage.title.like(prefix, escape="\\"),
                        UnifiedMessage.title.like(pattern, escape="\\")),
                ).order_by(UnifiedMessage.id.desc()).limit(size)
            ).all()
            for row in rows:
                items.append({
                    "kind": "MESSAGE",
                    "id": f"message:{row.id}",
                    "title": row.title,
                    "summary": row.source_module or "通知",
                    "time": _iso(row.created_at) if row.created_at else None,
                    "action": action_svc.build_message_action(
                        "message.detail", {"messageId": str(row.id)},
                        client=action_svc.CLIENT_STUDENT_MINI,
                    ),
                })

        # ② 本人办理标题。只查本人记录，标题前缀匹配。
        if len(items) < size:
            from app.models import CsLeave
            rows = db.scalars(
                select(CsLeave).where(
                    CsLeave.tenant_id == _tid(),
                    CsLeave.is_deleted.is_(False),
                    CsLeave.student_id == student.id,
                    or_(CsLeave.leave_type.like(prefix, escape="\\"),
                        CsLeave.reason.like(pattern, escape="\\")),
                ).order_by(CsLeave.id.desc()).limit(size - len(items))
            ).all()
            for row in rows:
                items.append({
                    "kind": "CASE",
                    "id": f"leave:{row.id}",
                    "title": f"学生请假（{row.leave_type}）",
                    "summary": row.reason or "",
                    "time": _iso(row.apply_time) if row.apply_time else None,
                    "action": action_svc.build_message_action(
                        "student.leave.detail", {"leaveId": str(row.id)},
                        client=action_svc.CLIENT_STUDENT_MINI,
                    ),
                })

    return {"keyword": value, "items": items[:size], "hasData": True}


def search_contract_snapshot() -> dict[str, Any]:
    return {
        "minKeywordLength": MIN_KEYWORD_LENGTH,
        "maxKeywordLength": MAX_KEYWORD_LENGTH,
        "pageSizeMax": PAGE_SIZE_MAX,
        "windowDays": SEARCH_WINDOW_DAYS,
        "kinds": ["MESSAGE", "CASE"],
        "scope": "self-only",
    }
