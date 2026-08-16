"""Graduation read-side organization scope guard.

The Graduation service historically inferred scope from a small set of role names. That
is unsafe once tenant-defined roles receive ``academicAffairs.graduation.view``: data
scope is an independent authority and must come from ``build_affairs_context``.

Current Graduation read contracts support school-wide and college-wide views. Narrower
CLASS/STUDENT/SELF scopes are intentionally fail-closed until a dedicated Graduation
contract defines those projections; they must never fall back to tenant-wide access.
"""
from __future__ import annotations

from app.core.affairs_security import build_affairs_context


def graduation_college_scope_ids(db, user) -> set[int] | None:
    """Return None for tenant-wide, college ids for COLLEGE, or empty for unsupported scope."""
    ctx = build_affairs_context(user or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return None
    if ctx.scope_type == "COLLEGE":
        return {int(value) for value in (ctx.college_ids or set())}
    return set()


graduation_college_scope_ids._graduation_scope_guard = True


def install(service) -> None:
    """Install the shared-context projection onto the existing Graduation service owner."""
    if getattr(getattr(service, "_college_scope_ids", None), "_graduation_scope_guard", False):
        return
    service._college_scope_ids = graduation_college_scope_ids
