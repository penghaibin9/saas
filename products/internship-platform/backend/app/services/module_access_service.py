from __future__ import annotations

from app.core.exceptions import AppException, no_permission

_ALLOWED_MODULE = "internship"


def assert_module_access(tenant_id: int, module_key: str, *, write: bool = False) -> dict:
    """Standalone only exposes the internship product.

    Commercial package/state decisions from the parent SaaS are intentionally not copied.
    A missing/invalid tenant fails closed; any non-internship module is denied.
    """
    try:
        tid = int(tenant_id or 0)
    except (TypeError, ValueError):
        tid = 0
    if tid <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少有效学校上下文", http_status=403)
    if str(module_key or "").strip() != _ALLOWED_MODULE:
        raise no_permission("Standalone 仅开放岗位实习模块")
    return {
        "tenantId": str(tid),
        "moduleKey": _ALLOWED_MODULE,
        "status": "ACTIVE",
        "readAllowed": True,
        "writeAllowed": True,
        "requestedWrite": bool(write),
    }


def module_access_state(tenant_id: int, module_key: str) -> dict:
    return assert_module_access(tenant_id, module_key, write=False)
