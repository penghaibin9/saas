from __future__ import annotations

from contextlib import contextmanager

from app.core.context import (
    get_current_user_ctx,
    get_tenant,
    set_current_user,
    set_tenant,
)

from .schemas import SearchContext


def search_context_is_authoritative(context: SearchContext) -> bool:
    """Require the actor and explicit query tenant to describe one tenant.

    Providers are private services and will eventually be called by several
    transports.  They therefore do not trust a caller-supplied tenant_id merely
    because the SQL itself is tenant-filtered.
    """
    raw_tenant = context.actor.get("tenantId") or context.actor.get("tenant_id")
    try:
        return int(context.tenant_id) > 0 and int(raw_tenant) == int(context.tenant_id)
    except (TypeError, ValueError):
        return False


@contextmanager
def explicit_search_context(context: SearchContext):
    """Install explicit tenant/actor values inside a federation worker thread."""
    previous_user = get_current_user_ctx()
    previous_tenant = get_tenant()
    set_current_user(dict(context.actor))
    set_tenant(int(context.tenant_id))
    try:
        yield
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)
