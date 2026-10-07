"""Standalone RBAC context consumed by the extracted admin/teacher PC shell.

The standalone product owns only the internship module. This endpoint projects the
same role permission patterns used by backend enforce_permission so frontend menu
and route UX cannot drift onto the parent SaaS /rbac/current-context contract.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.permissions import get_effective_access_context
from app.core.response import success
from app.core.security import get_current_user

router = APIRouter(prefix="/rbac", tags=["Standalone RBAC"])


@router.get("/current-context", summary="Standalone 当前角色、岗位实习权限与模块授权")
def current_context(user=Depends(get_current_user)):
    access = get_effective_access_context(user)
    role_code = str(access.get("roleCode") or "")
    role_name = str(
        (user or {}).get("currentRoleName")
        or (user or {}).get("roleName")
        or role_code
    )
    context_id = str(
        (user or {}).get("activeContextId")
        or (f"role-{role_code.lower()}" if role_code else "")
    )
    return success({
        "tenantId": str((user or {}).get("tenantId") or ""),
        "userId": str((user or {}).get("userId") or ""),
        "permissionPatterns": list(access.get("permissions") or []),
        "moduleEntitlements": ["internship"],
        "moduleStates": {"internship": "ACTIVE"},
        "moduleAccessHealthy": True,
        "moduleAccessError": "",
        "readonlyTenant": False,
        "currentRole": {
            "roleCode": role_code,
            "roleName": role_name,
            "contextId": context_id,
            "permissionVersion": str((user or {}).get("credentialVersion") or 0),
        },
    })
