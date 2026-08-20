"""Teacher Miniapp V3 T8 grouped Todo continuous reader.

This module does not create a second pagination or visibility authority. It reuses the
T2 signed-cursor/seek helpers and T3 SQL visibility compiler, while preserving the
existing teacher mobile FILTERS/_group_expr semantics from mobile_performance_service.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, select

from app.core.exceptions import AppException
from app.services import mobile_performance_service as perf
from app.services import teacher_mobile_todo_keyset_service as keyset
from app.services import workbench_todo_service as todo_svc
from app.services.db_service import _tid, session

_ALLOWED_GROUPS = {key for key, _ in perf.FILTERS}
_SORT_CONTRACT = "dueBucket:asc,dueAt:asc,id:desc"
_PAGE_SIZE_DEFAULT = 20
_PAGE_SIZE_MAX = 100


def _filter_hash(user: dict, *, group: str) -> str:
    payload = {
        "client": "teacherMini",
        "tenantId": int(_tid() or 0),
        "userId": int(todo_svc._uid(user) or 0),
        "group": group,
        "sort": _SORT_CONTRACT,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validation_error(message: str) -> AppException:
    return AppException("VALIDATION_ERROR", message, details={"reason": "INVALID_TODO_GROUP"})


def _normalize_group(value: str | None) -> str:
    group = str(value or "all").strip().lower() or "all"
    if group not in _ALLOWED_GROUPS:
        raise _validation_error("group 不合法")
    return group


def _filter_badges(db, UnifiedTodo, *, base: list, now) -> dict[str, int]:
    pending = UnifiedTodo.status == "PENDING"
    counts = {key: 0 for key, _ in perf.FILTERS}
    rows = db.execute(
        select(UnifiedTodo.todo_type, func.count())
        .where(*base, pending)
        .group_by(UnifiedTodo.todo_type)
    ).all()
    for todo_type, amount in rows:
        n = int(amount or 0)
        counts["all"] += n
        counts[perf._group_value(todo_type)] += n
    counts["done"] = int(db.scalar(
        select(func.count()).select_from(UnifiedTodo)
        .where(*base, UnifiedTodo.status == "DONE")
    ) or 0)
    counts["soon"] = int(db.scalar(
        select(func.count()).select_from(UnifiedTodo).where(
            *base,
            pending,
            UnifiedTodo.due_at.is_not(None),
            UnifiedTodo.due_at >= now,
            UnifiedTodo.due_at <= now + timedelta(hours=24),
        )
    ) or 0)
    return counts


def _group_conditions(UnifiedTodo, *, group: str, now) -> list[Any]:
    if group == "done":
        return [UnifiedTodo.status == "DONE"]

    conditions: list[Any] = [UnifiedTodo.status == "PENDING"]
    if group == "soon":
        conditions.extend([
            UnifiedTodo.due_at.is_not(None),
            UnifiedTodo.due_at >= now,
            UnifiedTodo.due_at <= now + timedelta(hours=24),
        ])
    elif group != "all":
        conditions.append(perf._group_expr() == group)
    return conditions


def list_grouped_continuous(
    user: dict,
    *,
    group: str = "all",
    cursor: str | None = None,
    page_size: int = _PAGE_SIZE_DEFAULT,
) -> dict[str, Any]:
    """Return one stable teacher Todo group page without OFFSET or client route guessing."""
    from app.models import UnifiedTodo

    current = perf._require_teacher(user)
    requested = _normalize_group(group)
    size = max(1, min(_PAGE_SIZE_MAX, int(page_size or _PAGE_SIZE_DEFAULT)))
    filter_hash = _filter_hash(current, group=requested)
    first_page = not bool(str(cursor or "").strip())

    cursor_payload: dict[str, Any] | None = None
    if first_page:
        as_of = todo_svc._utc_now()
        total = 0
        badges: dict[str, int] = {key: 0 for key, _ in perf.FILTERS}
    else:
        cursor_payload = keyset._decode_cursor(str(cursor), expected_filter_hash=filter_hash)
        as_of = keyset._parse_cursor_dt(cursor_payload.get("asOf"), field="asOf", required=True)
        total = int(cursor_payload.get("total") or 0)
        raw_badges = cursor_payload.get("filterBadges") or {}
        badges = {key: max(0, int(raw_badges.get(key) or 0)) for key, _ in perf.FILTERS}

    with session() as db:
        visibility = keyset._teacher_todo_visibility(current, UnifiedTodo)
        if visibility is None:
            return {
                "items": [],
                "filters": [{"key": key, "label": label, "badge": 0} for key, label in perf.FILTERS],
                "pendingCount": 0,
                "total": 0,
                "pageSize": size,
                "nextCursor": None,
                "hasMore": False,
                "filterHash": filter_hash,
                "asOf": keyset._iso_cursor_dt(as_of),
                "scopeMode": "FAIL_CLOSED",
            }

        base = [
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.created_at <= as_of,
            visibility,
        ]
        group_conds = _group_conditions(UnifiedTodo, group=requested, now=as_of)
        data_conds = [*base, *group_conds]

        if first_page:
            badges = _filter_badges(db, UnifiedTodo, base=base, now=as_of)
            total = int(db.scalar(
                select(func.count()).select_from(UnifiedTodo).where(*data_conds)
            ) or 0)

        due_bucket = case((UnifiedTodo.due_at.is_(None), 1), else_=0)
        if cursor_payload is not None:
            data_conds.append(keyset._seek_after(UnifiedTodo, bucket_expr=due_bucket, payload=cursor_payload))

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
            next_cursor = keyset._encode_cursor({
                "v": 1,
                "filterHash": filter_hash,
                "asOf": keyset._iso_cursor_dt(as_of),
                "dueBucket": 1 if last.due_at is None else 0,
                "dueAt": keyset._iso_cursor_dt(last.due_at),
                "id": int(last.id),
                "total": int(total),
                "statusCounts": {},
                "filterBadges": badges,
            })

        items = [todo_svc._todo_dict(row, client="teacherMini") for row in page_rows]

    return {
        "items": items,
        "filters": [{"key": key, "label": label, "badge": int(badges.get(key) or 0)} for key, label in perf.FILTERS],
        "pendingCount": int(badges.get("all") or 0),
        "total": int(total),
        "pageSize": size,
        "nextCursor": next_cursor,
        "hasMore": has_more,
        "filterHash": filter_hash,
        "asOf": keyset._iso_cursor_dt(as_of),
        "scopeMode": "TEACHER_SQL_VISIBILITY",
    }
