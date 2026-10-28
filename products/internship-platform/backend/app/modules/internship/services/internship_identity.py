"""Stable internship actor identity primitives.

Authorization must only use durable numeric user IDs. Display names and login names are
never authorization inputs. Browser/API DB subjects such as ``db-123`` are normalized to
``123`` without any database/name fallback.
"""
from __future__ import annotations


def stable_user_id(user) -> int | None:
    raw = str((user or {}).get("userId") or "").strip()
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value > 0 else None
