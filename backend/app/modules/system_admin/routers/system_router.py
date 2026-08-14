"""Control Plane adapters layered over the byte-frozen System bundle.

Only routes whose production semantics must change are replaced here. Every
other APIRoute object is reused verbatim from ``system_bundle``.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.permissions import require_any_permission, require_permission
from app.db.session import get_sessionmaker
from app.modules.system_admin.routers import system_bundle as _bundle

_replacements = APIRouter()


def _assert_permission_rows_exist(codes: set[str]) -> None:
    """Tenant runtime may consume Permission rows but may never create them."""
    concrete = sorted({c for c in codes if c and c != "*" and not c.endswith(".*") and not c.startswith("*.")})
    if not concrete:
        return
    from app.core.exceptions import AppException
    from app.models import Permission

    db = get_sessionmaker()()
    try:
        existing = set(db.scalars(select(Permission.permission_code).where(
            Permission.permission_code.in_(concrete)
        )).all())
    finally:
        db.close()
    missing = sorted(set(concrete) - existing)
    if missing:
        raise AppException(
            "PERMISSION_CATALOG_DRIFT",
            "权限目录与数据库未完成对账，学校运行时禁止创建全局权限",
            http_status=409,
            details={"missingPermissionCodes": missing[:50], "missingCount": len(missing)},
        )


def _assert_custom_role_catalog_policy(codes: set[str]) -> None:
    from app.core.permission_catalog import assert_custom_role_assignable

    assert_custom_role_assignable(codes, allow_legacy_patterns=True)


@_replacements.get("/system/context", summary="系统管理页上下文（品牌/角色/权限动作）")
def get_system_context(user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.user.view", "systemAdmin.role.view",
        "systemAdmin.org.view", "systemAdmin.audit.view", "systemAdmin.config.view",
        "systemAdmin.implementation.view", "systemAdmin.scope.view"))):
    """Preserve failure state and expose the canonical EffectiveAccess cache contract."""
    from app.core.effective_access import build_effective_access_context

    payload = _bundle.get_system_context(user=user)
    access = build_effective_access_context(user or {})
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            for key in (
                "principalPlane", "principalType", "subjectId", "tenantId", "activeContextId",
                "permissionPatterns", "permissionDigest", "permissionVersion", "securityRevision",
                "securityRevisionHealthy", "securityRevisionError", "ctxKey", "moduleEntitlements",
                "moduleStates", "moduleAccessHealthy", "moduleAccessError", "dataScopeSummary",
            ):
                data[key] = access.get(key)
    return payload


@_replacements.post("/system/roles/{role_id}/copy", summary="从预设或自定义角色复制学校自定义角色")
def copy_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.create"))):
    from app.core.exceptions import AppException
    from app.core.permissions import ROLE_PERMISSIONS
    from app.models import Permission, Role, RolePermission
    from app.services.system_admin_catalog_service import expand_permission_patterns

    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(Role).where(
            Role.id == role_id,
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        )).first()
        if source is None:
            raise AppException("DATA_NOT_FOUND", "源角色不存在")
        if str(source.role_code or "").upper().startswith("PLATFORM_"):
            raise AppException("NO_PERMISSION", "学校角色治理不能复制平台角色")
        if str(source.role_type or "").upper() == "SYSTEM":
            codes = set(expand_permission_patterns(set(ROLE_PERMISSIONS.get(source.role_code, set()))))
        else:
            codes = set(db.scalars(select(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id
            ).where(
                RolePermission.tenant_id == tenant_id,
                RolePermission.role_id == source.id,
                RolePermission.status == "ACTIVE",
                RolePermission.is_deleted.is_(False),
            )).all())
            codes = set(expand_permission_patterns(codes))
    finally:
        db.close()
    codes = {c for c in codes if c and c != "*" and not c.endswith(".*") and not c.startswith("*.")}
    _assert_custom_role_catalog_policy(codes)
    _assert_permission_rows_exist(codes)
    return _bundle.copy_system_role(role_id, user=user)


@_replacements.put("/system/roles/{role_id}/permissions", summary="保存自定义角色权限与默认范围")
def save_system_role_permissions(
    role_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.role.config")),
):
    from app.core.exceptions import AppException
    from app.services.system_admin_catalog_service import expand_permission_patterns

    raw_codes = body.get("permissionCodes") or []
    if not isinstance(raw_codes, list):
        raise AppException("VALIDATION_ERROR", "permissionCodes 必须为数组")
    codes = set(expand_permission_patterns({str(code).strip() for code in raw_codes if str(code).strip()}))
    codes = {c for c in codes if c != "*" and not c.endswith(".*") and not c.startswith("*.")}
    _assert_custom_role_catalog_policy(codes)
    _assert_permission_rows_exist(codes)
    return _bundle.save_system_role_permissions(role_id, body=body, user=user)


def _route_key(route) -> tuple[str, str]:
    methods = sorted(getattr(route, "methods", set()) or set())
    return (methods[0] if len(methods) == 1 else ",".join(methods), getattr(route, "path", ""))


def _compose_router() -> APIRouter:
    replacement_by_key = {_route_key(route): route for route in _replacements.routes}
    composed = APIRouter()
    routes = []
    for route in _bundle.router.routes:
        routes.append(replacement_by_key.pop(_route_key(route), route))
    if replacement_by_key:
        missing = sorted(replacement_by_key)
        raise RuntimeError(f"Control Plane replacement route has no legacy target: {missing}")
    composed.routes = routes
    return composed


router = _compose_router()
