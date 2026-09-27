"""消息中心统一用户 ID 解析。

令牌 userId 形态：
- db-123 → 123（正式账号）
- u_123 → 123（数字演示号）
- u_counselor01 等非数字 mock：优先按 loginName 查 t_user；仍无则用稳定 CRC（仅演示一致性，不冒充正式账号）
"""
from __future__ import annotations

import zlib
from typing import Any


def resolve_message_user_id(user: dict | None) -> int:
    raw = str((user or {}).get("userId") or "").strip()
    numeric_part = raw
    for prefix in ("db-", "u_"):
        if numeric_part.startswith(prefix):
            numeric_part = numeric_part[len(prefix):]
            break
    try:
        n = int(numeric_part)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass

    login = str((user or {}).get("loginName") or "").strip()
    if login:
        mapped = _lookup_user_id_by_login(user, login)
        if mapped:
            return mapped

    key = raw or login
    if not key:
        return 0
    # 演示账号无库映射时：同登录态读写一致，避免 inbox fail-closed / sender_user_id=0 对不上
    return (zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF) or 1


def _lookup_user_id_by_login(user: dict | None, login: str) -> int:
    try:
        from sqlalchemy import select
        from app.models import User
        from app.services.db_service import _tid, session
    except Exception:
        return 0
    try:
        tid = _tid()
    except Exception:
        tid = 0
        try:
            tid = int((user or {}).get("tenantId") or 0)
        except (TypeError, ValueError):
            tid = 0
    if not tid:
        return 0
    try:
        with session() as db:
            row = db.scalar(select(User.id).where(
                User.tenant_id == tid,
                User.login_name == login,
                User.is_deleted.is_(False),
            ))
            return int(row) if row else 0
    except Exception:
        return 0


def assert_positive_user_id(user: dict | None, *, action: str = "操作") -> int:
    uid = resolve_message_user_id(user)
    if not uid:
        from app.core.exceptions import AppException
        raise AppException(
            "UNAUTHORIZED",
            f"无法识别当前用户，不能{action}",
            details={"reason": "MESSAGE_USER_UNRESOLVED"},
        )
    return uid
