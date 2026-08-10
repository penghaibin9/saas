"""Stable audit actor identity for high-risk Stage C3 archive commands.

Real DB-backed authentication normally supplies a numeric ``userId``. Older signed
compatibility identities (including test-only mock login, which is disabled in
production) may carry values such as ``u_school_admin01``. Stage C3 still needs a
stable bigint to enforce creator != second approver and preserve immutable evidence.

Resolution order:
1. numeric authenticated userId;
2. tenant-scoped ``t_user.id`` by loginName;
3. deterministic 62-bit principal key from tenant + authenticated userId/loginName.

The final fallback is *not* a display-name guess and is never used as authorization;
permissions have already been checked by the canonical archive service. It only gives
legacy authenticated principals a repeatable audit identity so two-person approval can
be compared and persisted without NULL.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.services.db_service import _tid


def stable_actor_id(db=None) -> int | None:
    ctx = get_current_user_ctx() or {}
    raw = str(ctx.get("userId") or "").strip()
    try:
        numeric = int(raw) if raw else None
    except (TypeError, ValueError):
        numeric = None
    if numeric and numeric > 0:
        return numeric

    login = str(ctx.get("loginName") or "").strip()
    if db is not None and login:
        from app.models import User

        user_id = db.scalar(select(User.id).where(
            User.tenant_id == _tid(),
            User.login_name == login,
            User.is_deleted.is_(False),
        ))
        if user_id:
            return int(user_id)

    # Nonnumeric principal ids are accepted only after authentication/authorization.
    # Bind the key to tenant + exact authenticated subject to prevent cross-tenant
    # collisions and avoid relying on mutable display names.
    principal = raw or login
    if not principal:
        return None
    digest = hashlib.sha256(f"{_tid()}:{principal}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") & ((1 << 62) - 1)
    # Reserve a high bit inside the positive signed bigint range to distinguish these
    # compatibility actor keys from ordinary small autoincrement user ids.
    return (1 << 61) | value


def install(manifest_service) -> None:
    manifest_service._actor_id = stable_actor_id
