"""Teacher Miniapp V3 T2 continuous Todo keyset reader.

This module is deliberately additive: the legacy page/offset contract remains untouched,
and teacher-mobile gets a dedicated continuous-list reader. Route resolution still lives in
``workbench_todo_service`` / ``todo_route_registry``; this file owns only cursor semantics.

Cursor contract (V3 T2):
- signed opaque base64url JSON;
- binds to ``filterHash`` and the current teacher/tenant;
- freezes ``asOf`` for newly-created rows;
- carries ``dueBucket + dueAt + id`` as the exact seek tuple;
- carries first-page counts so later pages never repeat COUNT;
- every data page reads ``pageSize + 1`` rows to derive ``hasMore``.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import workbench_todo_service as todo_svc
from app.services.db_service import _tid, session

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 2048
_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 100
_ALLOWED_STATUS = {"PENDING", "DONE", "CANCELLED"}
_SORT_CONTRACT = "dueBucket:asc,dueAt:asc,id:desc"


def _validation_error(message: str) -> AppException:
    return AppException("VALIDATION_ERROR", message, details={"reason": "INVALID_TODO_CURSOR"})


def _normalize_status(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper() or None
    if normalized and normalized not in _ALLOWED_STATUS:
        raise _validation_error("待办状态不合法")
    return normalized


def _normalize_todo_type(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper() or None
    if normalized and len(normalized) > 100:
        raise _validation_error("待办类型过长")
    return normalized


def _iso_cursor_dt(value: datetime | None) -> str | None:
    return value.isoformat(timespec="microseconds") if value else None


def _parse_cursor_dt(value: Any, *, field: str, required: bool = True) -> datetime | None:
    if value in (None, ""):
        if required:
            raise _validation_error(f"cursor 缺少 {field}")
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise _validation_error(f"cursor {field} 不合法") from exc
    # Repository timestamps are naive UTC. Reject offset-aware cursor values instead of
    # mixing aware/naive comparisons and silently shifting the seek boundary.
    if parsed.tzinfo is not None:
        raise _validation_error(f"cursor {field} 时区格式不合法")
    return parsed


def _filter_hash(user: dict, *, status: str | None, todo_type: str | None) -> str:
    payload = {
        "client": "teacherMini",
        "tenantId": int(_tid() or 0),
        "userId": int(todo_svc._uid(user) or 0),
        "status": status or "",
        "todoType": todo_type or "",
        "sort": _SORT_CONTRACT,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode((token + padding).encode("ascii"))


def _cursor_signature(raw: bytes) -> bytes:
    secret = str(settings.jwt_secret or "").encode("utf-8")
    if not secret:
        raise AppException("SERVER_ERROR", "游标签名密钥未配置", details={"reason": "CURSOR_SIGNING_KEY_MISSING"})
    return hmac.new(secret, raw, hashlib.sha256).digest()


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64encode(raw)}.{_b64encode(_cursor_signature(raw))}"


def _decode_cursor(cursor: str, *, expected_filter_hash: str) -> dict[str, Any]:
    token = str(cursor or "").strip()
    if not token or len(token) > _MAX_CURSOR_LENGTH or token.count(".") != 1:
        raise _validation_error("cursor 为空、过长或格式不合法")
    try:
        body_token, signature_token = token.split(".", 1)
        raw = _b64decode(body_token)
        supplied_signature = _b64decode(signature_token)
        if not hmac.compare_digest(supplied_signature, _cursor_signature(raw)):
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

    bucket = payload.get("dueBucket")
    try:
        bucket = int(bucket)
        row_id = int(payload.get("id") or 0)
        total = int(payload.get("total") or 0)
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor 排序键不合法") from exc
    if bucket not in (0, 1) or row_id <= 0 or total < 0:
        raise _validation_error("cursor 排序键不合法")

    _parse_cursor_dt(payload.get("asOf"), field="asOf", required=True)
    if bucket == 0:
        _parse_cursor_dt(payload.get("dueAt"), field="dueAt", required=True)
    elif payload.get("dueAt") not in (None, ""):
        raise _validation_error("无截止时间分桶不得携带 dueAt")

    status_counts = payload.get("statusCounts") or {}
    if not isinstance(status_counts, dict):
        raise _validation_error("cursor 计数快照不合法")
    validated_counts: dict[str, int] = {}
    try:
        for key, value in status_counts.items():
            name = str(key)
            if name not in _ALLOWED_STATUS:
                continue
            count = int(value or 0)
            if count < 0:
                raise ValueError("negative count")
            validated_counts[name] = count
    except (TypeError, ValueError) as exc:
        raise _validation_error("cursor 计数快照不合法") from exc

    payload["dueBucket"] = bucket
    payload["id"] = row_id
    payload["total"] = total
    payload["statusCounts"] = validated_counts
    return payload


def _first_page_counts(db, UnifiedTodo, *, base_conds: list, status: str | None) -> tuple[int, dict[str, int]]:
    """Compute total + status buckets exactly once, on the first cursor page."""
    total_conds = list(base_conds)
    if status:
        total_conds.append(UnifiedTodo.status == status)
    total = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(*total_conds)) or 0)
    rows = db.execute(
        select(UnifiedTodo.status, func.count())
        .where(*base_conds)
        .group_by(UnifiedTodo.status)
    ).all()
    counts = {str(key): int(value or 0) for key, value in rows if str(key) in _ALLOWED_STATUS}
    return total, counts


def _seek_after(UnifiedTodo, *, bucket_expr, payload: dict[str, Any]):
    bucket = int(payload["dueBucket"])
    row_id = int(payload["id"])
    if bucket == 1:
        return and_(bucket_expr == 1, UnifiedTodo.id < row_id)

    due_at = _parse_cursor_dt(payload.get("dueAt"), field="dueAt", required=True)
    return or_(
        bucket_expr > 0,
        and_(bucket_expr == 0, UnifiedTodo.due_at > due_at),
        and_(bucket_expr == 0, UnifiedTodo.due_at == due_at, UnifiedTodo.id < row_id),
    )


def list_continuous(
    user: dict,
    *,
    status: str | None = None,
    todo_type: str | None = None,
    cursor: str | None = None,
    page_size: int = _PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    """Read one stable seek page without OFFSET and without repeated COUNT."""
    from app.models import UnifiedTodo

    size = max(1, min(_PAGE_SIZE_MAX, int(page_size or _PAGE_SIZE_DEFAULT)))
    normalized_status = _normalize_status(status)
    normalized_type = _normalize_todo_type(todo_type)
    filter_hash = _filter_hash(user, status=normalized_status, todo_type=normalized_type)
    first_page = not bool(str(cursor or "").strip())

    cursor_payload: dict[str, Any] | None = None
    if first_page:
        as_of = datetime.utcnow()
        total = 0
        status_counts: dict[str, int] = {}
    else:
        cursor_payload = _decode_cursor(str(cursor), expected_filter_hash=filter_hash)
        as_of = _parse_cursor_dt(cursor_payload.get("asOf"), field="asOf", required=True)
        total = int(cursor_payload.get("total") or 0)
        status_counts = dict(cursor_payload.get("statusCounts") or {})

    with session() as db:
        visibility = todo_svc._visibility_cond(db, user)
        if visibility is None:
            return {
                "items": [],
                "total": 0,
                "pageSize": size,
                "nextCursor": None,
                "hasMore": False,
                "statusCounts": {},
                "filterHash": filter_hash,
                "asOf": _iso_cursor_dt(as_of),
            }

        base_conds = [
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.created_at <= as_of,
            visibility,
        ]
        if normalized_type:
            base_conds.append(UnifiedTodo.todo_type == normalized_type)

        if first_page:
            total, status_counts = _first_page_counts(
                db, UnifiedTodo, base_conds=base_conds, status=normalized_status
            )

        data_conds = list(base_conds)
        if normalized_status:
            data_conds.append(UnifiedTodo.status == normalized_status)

        due_bucket = case((UnifiedTodo.due_at.is_(None), 1), else_=0)
        if cursor_payload is not None:
            data_conds.append(_seek_after(UnifiedTodo, bucket_expr=due_bucket, payload=cursor_payload))

        rows = db.scalars(
            select(UnifiedTodo)
            .where(*data_conds)
            .order_by(due_bucket.asc(), UnifiedTodo.due_at.asc(), UnifiedTodo.id.desc())
            .limit(size + 1)
        ).all()
        has_more = len(rows) > size
        page_rows = rows[:size]

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor({
                "v": _CURSOR_VERSION,
                "filterHash": filter_hash,
                "asOf": _iso_cursor_dt(as_of),
                "dueBucket": 1 if last.due_at is None else 0,
                "dueAt": _iso_cursor_dt(last.due_at),
                "id": int(last.id),
                "total": int(total),
                "statusCounts": status_counts,
            })

        return {
            "items": [todo_svc._todo_dict(row, client="teacherMini") for row in page_rows],
            "total": int(total),
            "pageSize": size,
            "nextCursor": next_cursor,
            "hasMore": has_more,
            "statusCounts": status_counts,
            "filterHash": filter_hash,
            "asOf": _iso_cursor_dt(as_of),
        }
