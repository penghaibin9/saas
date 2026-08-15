"""Control Plane adapters layered over the byte-frozen System bundle.

Only routes whose production semantics must change are replaced here. Every
other APIRoute object is reused verbatim from ``system_bundle``.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.modules.system_admin.routers import school_iam_router as _school_iam
from app.modules.system_admin.routers import system_bundle as _bundle

_replacements = APIRouter()
_EFFECTIVE_ACCESS_KEYS = (
    "principalPlane", "principalType", "subjectId", "tenantId", "activeContextId",
    "permissionPatterns", "permissionDigest", "permissionVersion", "securityRevision",
    "securityRevisionHealthy", "securityRevisionError", "ctxKey", "moduleEntitlements",
    "moduleStates", "moduleAccessHealthy", "moduleAccessError", "dataScopeSummary",
)


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


def _runtime_role_permission_codes(db, role, *, tenant_id: int) -> set[str]:
    """Resolve the one runtime Authority for a role being persisted/delegated."""
    from app.services import system_role_shadow_service as shadow

    role_code = str(role.role_code or "").strip().upper()
    if role_code.startswith("PLATFORM_"):
        from app.core.exceptions import AppException

        raise AppException("NO_PERMISSION", "学校角色治理不能授予平台角色")
    if str(role.role_type or "").upper() == "SYSTEM":
        return set(shadow.published_system_role_permissions(db, role_code))
    return set(shadow.custom_role_permission_codes(
        db,
        tenant_id=int(tenant_id),
        role_id=int(role.id),
    ))


def _custom_role_source_snapshot(db, source, *, tenant_id: int) -> tuple[str, int]:
    """Pin compatibility copies to the same immutable delivered-template lineage."""
    from app.core.exceptions import AppException
    from app.models.permission_governance import (
        TEMPLATE_CATEGORY_SYSTEM_ROLE,
        TEMPLATE_PLANE_TENANT,
        TEMPLATE_PUBLISHED,
        CustomRoleSource,
        RoleTemplate,
    )

    if str(source.role_type or "").upper() == "SYSTEM":
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == str(source.role_code or "").strip().upper(),
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
            RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
        if template is None:
            raise AppException(
                "B8_SYSTEM_TEMPLATE_DRIFT",
                "SYSTEM 角色缺少已发布 Control Plane Authority 模板",
                http_status=409,
                details={"roleCode": source.role_code},
            )
        return str(template.template_code), int(template.template_version or 1)

    source_binding = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == int(tenant_id),
        CustomRoleSource.role_id == int(source.id),
        CustomRoleSource.role_code == source.role_code,
        CustomRoleSource.is_deleted.is_(False),
    )).first()
    if source_binding is None:
        raise AppException(
            "CUSTOM_ROLE_BINDING_DRIFT",
            "CUSTOM 角色缺少稳定 Role ↔ CustomRoleSource 绑定",
            http_status=409,
            details={"tenantId": int(tenant_id), "roleId": int(source.id)},
        )
    return str(source_binding.source_template_code), int(source_binding.source_template_version or 1)


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
            for key in _EFFECTIVE_ACCESS_KEYS:
                data[key] = access.get(key)
            actions = data.get("permissionActions")
            if not isinstance(actions, dict):
                actions = {}
                data["permissionActions"] = actions
            actions["effectiveAccess"] = {key: access.get(key) for key in _EFFECTIVE_ACCESS_KEYS}
    return payload


@_replacements.put("/system/users/{user_id}/roles", summary="分配学校账号角色")
def assign_system_user_roles(
    user_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.user.assign-role")),
):
    """Persist role membership only after canonical target-role Authority validation."""
    from app.core.exceptions import AppException
    from app.core.permissions import assert_delegable_permission_codes
    from app.models import Role, User, UserRole

    tenant_id = int(current_tenant_id() or 0)
    codes = sorted({
        str(code).strip().upper()
        for code in (body.get("roleCodes") or [])
        if str(code).strip()
    })
    if not codes:
        raise AppException("VALIDATION_ERROR", "至少保留一个角色")

    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在")
        if _bundle._account_type_of(account, db) == "STUDENT":
            if codes != ["STUDENT"]:
                raise AppException("NO_PERMISSION", "学生账号固定绑定 STUDENT，禁止分配教职工或管理员角色")
        elif "STUDENT" in codes:
            raise AppException("VALIDATION_ERROR", "教职工账号不能绑定 STUDENT 角色")
        if "SCHOOL_ADMIN" not in codes and _bundle._is_last_active_school_admin(db, tenant_id, account.id):
            raise AppException("VALIDATION_ERROR", "不能移除本校最后一名启用中的学校管理员")

        roles = list(db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(codes),
            Role.status.in_(("ACTIVE", "ENABLED")),
            Role.is_deleted.is_(False),
        )).all())
        if len(roles) != len(codes):
            raise AppException("VALIDATION_ERROR", "包含不存在或已停用的角色")

        for role_obj in roles:
            patterns = _runtime_role_permission_codes(db, role_obj, tenant_id=tenant_id)
            try:
                assert_delegable_permission_codes(user, patterns)
            except AppException as exc:
                if exc.code == "NO_PERMISSION":
                    raise AppException(
                        "NO_PERMISSION",
                        f"不能分配超出自身基础权限边界的角色：{role_obj.role_name}",
                    ) from None
                raise

        existing = {
            link.role_id: link
            for link in db.scalars(select(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == account.id,
            )).all()
        }
        wanted = {role_obj.id for role_obj in roles}
        for role_id, link in existing.items():
            if role_id in wanted:
                link.status = "ACTIVE"
                link.is_deleted = False
            else:
                link.status = "DISABLED"
                link.is_deleted = True
            link.version = int(link.version or 0) + 1
        for role_id in wanted - set(existing):
            db.add(UserRole(
                tenant_id=tenant_id,
                user_id=account.id,
                role_id=role_id,
                status="ACTIVE",
            ))
        account.version = int(account.version or 0) + 1

        from app.services import audit_log

        audit_log.record_critical_in_session(
            db,
            "USER_ROLE_ASSIGN",
            f"user:{account.id}",
            detail={
                "loginName": account.login_name,
                "roleCodes": codes,
                "moduleCode": "systemAdmin",
                "authoritySource": "PUBLISHED_ROLE_TEMPLATE_OR_CUSTOM_ROLE_PERMISSION",
            },
            tenant_id=tenant_id,
            resource_id=str(account.id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services.auth_service_db import invalidate_subject_cache

    invalidate_subject_cache(f"db-{int(user_id)}", tenant_id)
    return success(
        {"id": str(user_id), "roleCodes": codes},
        message="角色已分配；该账号需重新登录",
    )


@_replacements.post("/system/roles/{role_id}/copy", summary="从预设或自定义角色复制学校自定义角色")
def copy_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.create"))):
    """Compatibility copy with canonical Authority, no runtime Permission creation."""
    from app.core.exceptions import AppException
    from app.core.permissions import assert_delegable_permission_codes
    from app.models import Permission, Role, RolePermission
    from app.models.permission_governance import CustomRoleSource

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(Role).where(
            Role.id == int(role_id),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        )).first()
        if source is None:
            raise AppException("DATA_NOT_FOUND", "源角色不存在")

        codes = {
            code for code in _runtime_role_permission_codes(db, source, tenant_id=tenant_id)
            if code and code != "*" and not code.endswith(".*") and not code.startswith("*.")
        }

        # Permanent delegation boundary wins over catalog-drift diagnostics: a
        # temporary grant may never be persisted even when the catalog is dirty.
        assert_delegable_permission_codes(user, codes)
        _assert_custom_role_catalog_policy(codes)

        existing_permission_codes = set(db.scalars(select(Permission.permission_code).where(
            Permission.permission_code.in_(sorted(codes))
        )).all()) if codes else set()
        missing = sorted(codes - existing_permission_codes)
        if missing:
            raise AppException(
                "PERMISSION_CATALOG_DRIFT",
                "权限目录与数据库未完成对账，学校运行时禁止创建全局权限",
                http_status=409,
                details={"missingPermissionCodes": missing[:50], "missingCount": len(missing)},
            )

        source_template_code, source_template_version = _custom_role_source_snapshot(
            db, source, tenant_id=tenant_id,
        )
        base = re.sub(
            r"[^A-Z0-9_]",
            "_",
            f"{source.role_code}_CUSTOM",
        )[:44].rstrip("_") or "CUSTOM"
        existing_codes = set(db.scalars(select(Role.role_code).where(
            Role.tenant_id == tenant_id
        )).all())
        code = next((
            f"{base}_{index}"
            for index in range(1, 1000)
            if f"{base}_{index}" not in existing_codes
        ), None)
        if code is None:
            raise AppException("DATA_CONFLICT", "无法生成可用的角色编码")

        role = Role(
            tenant_id=tenant_id,
            role_code=code,
            role_name=f"{source.role_name}（自定义）",
            role_type="CUSTOM",
            status="ACTIVE",
            remark="SAAS_CUSTOM;authority=CONTROL_PLANE",
        )
        _bundle._set_role_scope(role, _bundle._role_scope(source), user=user)
        db.add(role)
        db.flush()

        db.add(CustomRoleSource(
            tenant_id=tenant_id,
            role_id=int(role.id),
            role_code=code,
            source_template_code=source_template_code,
            source_template_version=source_template_version,
            permission_codes_json={"items": sorted(codes)},
            drift_json={"compatibilityCopy": True, "authority": "CONTROL_PLANE"},
            status="ACTIVE",
        ))

        permissions = {
            row.permission_code: row
            for row in db.scalars(select(Permission).where(
                Permission.permission_code.in_(sorted(codes))
            )).all()
        } if codes else {}
        for permission_code in sorted(codes):
            db.add(RolePermission(
                tenant_id=tenant_id,
                role_id=int(role.id),
                permission_id=int(permissions[permission_code].id),
                status="ACTIVE",
            ))

        from app.services import audit_log

        audit_log.record_critical_in_session(
            db,
            "ROLE_COPY",
            f"role:{role.id}",
            detail={
                "sourceRoleId": str(source.id),
                "sourceRoleCode": source.role_code,
                "roleCode": role.role_code,
                "permissionCount": len(codes),
                "moduleCode": "systemAdmin",
                "authoritySource": "PUBLISHED_ROLE_TEMPLATE_OR_CUSTOM_ROLE_PERMISSION",
            },
            tenant_id=tenant_id,
            resource_id=str(role.id),
        )
        db.commit()
        db.refresh(role)
        return success(_bundle._role_row(role, 0), message="已复制为自定义角色；成员未复制")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
    school_keys = {_route_key(route) for route in _school_iam.router.routes}
    existing_keys = {_route_key(route) for route in routes}
    collisions = sorted(school_keys & existing_keys)
    if collisions:
        raise RuntimeError(f"School IAM route collision: {collisions}")
    routes.extend(_school_iam.router.routes)
    composed.routes = routes
    return composed


router = _compose_router()
