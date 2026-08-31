"""Control Plane adapters layered over the byte-frozen System bundle.

Only routes whose production semantics must change are replaced here. Every
other APIRoute object is reused verbatim from ``system_bundle``.
"""
from __future__ import annotations

import re
import uuid

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
            role_options = ((data.get("filterOptions") or {}).get("roles") or [])
            role_codes = {
                str(option.get("value") or "").strip().upper()
                for option in role_options if isinstance(option, dict)
            }
            if role_codes:
                from app.models import Role
                from app.services.role_assignment_scope_service import role_scope_policy

                db = get_sessionmaker()()
                try:
                    roles = db.scalars(select(Role).where(
                        Role.tenant_id == int(current_tenant_id() or 0),
                        Role.role_code.in_(role_codes),
                        Role.status.in_(("ACTIVE", "ENABLED")),
                        Role.is_deleted.is_(False),
                    )).all()
                    policies = {
                        str(role.role_code).upper(): role_scope_policy(db, role)
                        for role in roles
                    }
                    for option in role_options:
                        if not isinstance(option, dict):
                            continue
                        policy = policies.get(str(option.get("value") or "").upper())
                        if policy:
                            option.update(policy)
                finally:
                    db.close()
            for key in _EFFECTIVE_ACCESS_KEYS:
                data[key] = access.get(key)
            actions = data.get("permissionActions")
            if not isinstance(actions, dict):
                actions = {}
                data["permissionActions"] = actions
            actions["effectiveAccess"] = {key: access.get(key) for key in _EFFECTIVE_ACCESS_KEYS}
    return payload


@_replacements.get("/system/users/{user_id}", summary="学校账号详情（真实库）")
def get_system_user(
    user_id: int,
    user=Depends(require_permission("systemAdmin.user.view")),
):
    """Layer the editable role-scope contract over the byte-frozen detail endpoint."""
    from app.models import Role, User, UserRole
    from app.services.role_assignment_scope_service import assignment_payload

    payload = _bundle.get_system_user(user_id, user=user)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return payload

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        )).first()
        if account is None:
            return payload
        role_links = db.execute(select(UserRole, Role).join(
            Role, Role.id == UserRole.role_id,
        ).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == int(user_id),
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.status.in_(("ACTIVE", "ENABLED")),
            Role.is_deleted.is_(False),
        )).all()
        data["roleAssignments"] = [
            assignment_payload(
                db, account=account, role=role, user_role_id=int(link.id),
            )
            for link, role in role_links
        ]
        return payload
    finally:
        db.close()


@_replacements.get("/system/roles/{role_id}", summary="学校角色详情（Control Plane Authority）")
def get_system_role(
    role_id: int,
    user=Depends(require_permission("systemAdmin.role.view")),
):
    """Project the same role Authority used by assignment and authorization."""
    from app.core.exceptions import AppException
    from app.core.permission_catalog import permission_meta
    from app.models import Role
    from app.services.system_admin_catalog_service import (
        build_permission_tree,
        split_selection,
        visible_codes_from_tree,
    )

    payload = _bundle.get_system_role(role_id, user=user)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return payload

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(
            Role.id == int(role_id),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        )).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        permission_codes = sorted(_runtime_role_permission_codes(db, role, tenant_id=tenant_id))
        tree = build_permission_tree(user)
        visible = visible_codes_from_tree(tree)
        selection = split_selection(permission_codes, tree)
        read_only = []
        legacy = []
        unmapped = []
        for code in sorted(set(permission_codes) - visible):
            meta = permission_meta(code)
            if code.startswith("system."):
                reason = "legacy compatibility；新写入只允许 systemAdmin.*"
                legacy.append(code)
            elif meta is None:
                reason = "未映射到 ACTIVE Permission Catalog"
                unmapped.append(code)
            elif not bool(meta.get("customRoleAssignable")):
                reason = "Permission Catalog 标记为不可由 Custom Role 分配"
            else:
                reason = "超出当前操作者永久授权上限"
            read_only.append({"permissionCode": code, "reason": reason})

        data.update({
            "version": int(role.version or 0),
            "permissionCodes": permission_codes,
            "menuKeys": selection["menuKeys"],
            "buttonKeys": selection["buttonKeys"],
            "editablePermissionCodes": sorted(set(permission_codes) & visible),
            "readOnlyPreservedPermissions": read_only,
            "readOnlyPreservedPermissionCodes": [item["permissionCode"] for item in read_only],
            "legacyPermissionCodes": legacy,
            "unmappedPermissionCodes": unmapped,
            "permissionAuthority": (
                "PUBLISHED_ROLE_TEMPLATE"
                if str(role.role_type or "").upper() == "SYSTEM"
                else "ROLE_PERMISSION_PINNED"
            ),
        })
        return payload
    finally:
        db.close()


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
            link = UserRole(
                tenant_id=tenant_id,
                user_id=account.id,
                role_id=role_id,
                status="ACTIVE",
            )
            db.add(link)
            existing[role_id] = link
        db.flush()

        scope_result = []
        if "roleAssignments" in body:
            from app.services.role_assignment_scope_service import sync_assignment_scopes
            scope_result = sync_assignment_scopes(
                db,
                account=account,
                roles=roles,
                links_by_role_id=existing,
                raw_assignments=body.get("roleAssignments"),
                actor=user,
            )
        else:
            from app.services.role_assignment_scope_service import revoke_removed_role_scopes
            revoke_removed_role_scopes(
                db, tenant_id=tenant_id, user_id=int(account.id),
                active_role_codes=set(codes), actor=user,
            )
        account.version = int(account.version or 0) + 1

        from app.services import audit_log

        audit_log.record_critical_in_session(
            db,
            "USER_ROLE_ASSIGN",
            f"user:{account.id}",
            detail={
                "loginName": account.login_name,
                "roleCodes": codes,
                "roleAssignments": scope_result,
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
        {"id": str(user_id), "roleCodes": codes, "roleAssignments": scope_result},
        message="角色已分配；该账号需重新登录",
    )


@_replacements.post("/system/roles", summary="创建学校自定义角色")
def create_system_role(
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.role.create")),
):
    """Create the runtime identity and its stable pinned source atomically."""
    import secrets

    from app.core.exceptions import AppException
    from app.models import CustomRoleSource, Role, RoleTemplate
    from app.models.permission_governance import (
        TEMPLATE_CATEGORY_SYSTEM_ROLE,
        TEMPLATE_PLANE_TENANT,
        TEMPLATE_PUBLISHED,
    )
    from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code

    tenant_id = int(current_tenant_id() or 0)
    name = str(body.get("name") or "").strip()
    code = str(body.get("code") or "").strip().upper() or f"CUSTOM_{secrets.token_hex(4).upper()}"
    if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,49}", code):
        raise AppException("VALIDATION_ERROR", "角色名称必填，编码须为 3-50 位大写字母、数字或下划线")

    db = get_sessionmaker()()
    try:
        if db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code == code,
        )).first():
            raise AppException("DATA_CONFLICT", "角色编码已存在")
        source_template_code = assert_school_role_template_code(
            body.get("sourceTemplateCode") or "SCHOOL_ADMIN"
        )
        source_template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == source_template_code,
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
            RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
        if source_template is None:
            raise AppException(
                "B8_SYSTEM_TEMPLATE_DRIFT",
                "自定义角色必须固定到已发布学校角色模板",
                http_status=409,
                details={"sourceTemplateCode": source_template_code},
            )
        role = Role(
            tenant_id=tenant_id,
            role_code=code,
            role_name=name,
            role_type="CUSTOM",
            status="ACTIVE",
            remark="SAAS_CUSTOM;authority=CONTROL_PLANE",
        )
        db.add(role)
        db.flush()
        from app.services.data_scope_service import save_role_scope_in_session

        save_role_scope_in_session(
            db,
            role,
            body.get("scopeCode") or "ASSIGNED",
            target_json=(
                body["scopeTarget"]
                if "scopeTarget" in body
                else body.get("targetJson")
            ),
        )
        db.add(CustomRoleSource(
            tenant_id=tenant_id,
            role_id=int(role.id),
            role_code=code,
            source_template_code=source_template_code,
            source_template_version=int(source_template.template_version or 1),
            permission_codes_json={"items": []},
            drift_json={"policy": "PINNED", "automaticUpgrade": False},
            status="ACTIVE",
        ))

        from app.services import audit_log

        audit_log.record_critical_in_session(
            db,
            "ROLE_CREATE",
            f"role:{role.id}",
            detail={
                "roleCode": code,
                "roleName": name,
                "moduleCode": "systemAdmin",
                "authoritySource": "ROLE_PERMISSION_PINNED",
            },
            tenant_id=tenant_id,
            resource_id=str(role.id),
        )
        db.commit()
        db.refresh(role)
        return success(_bundle._role_row(role, 0), message="自定义角色已创建；请继续配置权限")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@_replacements.post("/system/roles/{role_id}/copy", summary="从预设或自定义角色复制学校自定义角色")
def copy_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.create"))):
    """Compatibility copy with canonical Authority, no runtime Permission creation."""
    from app.core.exceptions import AppException
    from app.core.permissions import assert_delegable_permission_codes
    from app.models import DataScopeRule, Permission, Role, RolePermission
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
        source_scope_rule = db.scalars(select(DataScopeRule).where(
            DataScopeRule.tenant_id == tenant_id,
            DataScopeRule.role_code == source.role_code,
            DataScopeRule.status == "ACTIVE",
            DataScopeRule.is_deleted.is_(False),
        ).order_by(DataScopeRule.id.desc()).limit(1)).first()
        source_scope_code = (
            str(source_scope_rule.scope_type)
            if source_scope_rule is not None
            else _bundle._role_scope(source)
        )
        source_scope_target = (
            dict(source_scope_rule.target_json or {})
            if source_scope_rule is not None
            else {}
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
        db.add(role)
        db.flush()
        from app.services.data_scope_service import save_role_scope_in_session

        save_role_scope_in_session(
            db,
            role,
            source_scope_code,
            target_json=source_scope_target,
        )

        db.add(CustomRoleSource(
            tenant_id=tenant_id,
            role_id=int(role.id),
            role_code=code,
            source_template_code=source_template_code,
            source_template_version=source_template_version,
            permission_codes_json={"items": sorted(codes)},
            drift_json={
                "compatibilityCopy": True,
                "authority": "CONTROL_PLANE",
                "policy": "DERIVED_PINNED",
                "automaticUpgrade": False,
            },
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
    import hashlib
    import json

    from sqlalchemy import func

    from app.core.exceptions import AppException
    from app.core.permission_catalog import permission_meta
    from app.core.permissions import assert_delegable_permission_codes
    from app.models import CustomRoleSource, Permission, Role, RolePermission, UserRole
    from app.services.system_admin_catalog_service import (
        build_permission_tree,
        expand_permission_patterns,
        visible_codes_from_tree,
    )

    raw_codes = body.get("permissionCodes") or []
    if not isinstance(raw_codes, list):
        raise AppException("VALIDATION_ERROR", "permissionCodes 必须为数组")
    raw_code_set = {str(code).strip() for code in raw_codes if str(code).strip()}
    legacy_writes = sorted(code for code in raw_code_set if code.startswith("system."))
    if legacy_writes:
        raise AppException(
            "LEGACY_PERMISSION_WRITE_FORBIDDEN",
            "新角色写入只允许 canonical systemAdmin.* 权限码",
            http_status=422,
            details={"permissionCodes": legacy_writes[:50]},
        )
    codes = set(expand_permission_patterns(raw_code_set))
    codes = {c for c in codes if c != "*" and not c.endswith(".*") and not c.startswith("*.")}
    # A temporary grant must never become durable.  Enforce that security
    # boundary before request-shape/catalog diagnostics so callers cannot use
    # validation precedence to probe or persist delegated capabilities.
    assert_delegable_permission_codes(user, codes)
    _assert_custom_role_catalog_policy(codes)
    if body.get("expectedVersion") is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 必填", http_status=422)
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "权限变更原因至少 5 个字符", http_status=422)
    request_id = str(body.get("requestId") or "").strip()
    try:
        uuid.UUID(request_id)
    except (ValueError, TypeError, AttributeError):
        raise AppException("VALIDATION_ERROR", "requestId 必须是 UUID", http_status=422)
    visible = visible_codes_from_tree(build_permission_tree(user))
    if not codes <= visible:
        raise AppException(
            "PERMISSION_AUTHORING_BOUNDARY",
            "提交权限超出服务端可配置集合",
            http_status=422,
            details={"permissionCodes": sorted(codes - visible)[:50]},
        )

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(
            Role.id == int(role_id),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        ).with_for_update()).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色由平台模板维护；请复制为自定义角色后再裁剪")
        if int(role.version or 0) != int(body["expectedVersion"]):
            raise AppException("DATA_CONFLICT", "角色权限已被他人修改，请刷新后重试", http_status=409)

        source = db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tenant_id,
            CustomRoleSource.role_id == int(role.id),
            CustomRoleSource.role_code == role.role_code,
            CustomRoleSource.is_deleted.is_(False),
        ).with_for_update()).first()
        if source is None:
            raise AppException(
                "CUSTOM_ROLE_BINDING_DRIFT",
                "CUSTOM 角色缺少稳定 Role ↔ CustomRoleSource 绑定",
                http_status=409,
                details={"tenantId": tenant_id, "roleId": int(role.id)},
            )

        existing_links = list(db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == int(role.id),
        )).all())
        existing_codes_by_id = {
            int(permission.id): str(permission.permission_code)
            for permission in db.scalars(select(Permission).join(
                RolePermission, RolePermission.permission_id == Permission.id,
            ).where(
                RolePermission.tenant_id == tenant_id,
                RolePermission.role_id == int(role.id),
            )).all()
        }
        existing_codes = {
            existing_codes_by_id[int(link.permission_id)]
            for link in existing_links
            if link.status == "ACTIVE" and not link.is_deleted and int(link.permission_id) in existing_codes_by_id
        }
        preserved = {code for code in existing_codes if code not in visible}
        final_codes = sorted(preserved | codes)
        permissions = {
            item.permission_code: item
            for item in db.scalars(select(Permission).where(
                Permission.permission_code.in_(final_codes)
            )).all()
        } if final_codes else {}
        missing = sorted(set(final_codes) - set(permissions))
        if missing:
            raise AppException(
                "PERMISSION_CATALOG_DRIFT",
                "角色权限缺少预置 Permission 行，学校运行时禁止创建",
                http_status=409,
                details={"permissionCodes": missing[:50]},
            )

        existing_by_permission_id = {int(link.permission_id): link for link in existing_links}
        wanted_ids = {int(permissions[code].id) for code in final_codes}
        for permission_id, link in existing_by_permission_id.items():
            code = existing_codes_by_id.get(permission_id, "")
            if permission_id in wanted_ids:
                link.status = "ACTIVE"
                link.is_deleted = False
            elif code in visible:
                link.status = "DISABLED"
                link.is_deleted = True
        for permission_id in wanted_ids - set(existing_by_permission_id):
            db.add(RolePermission(
                tenant_id=tenant_id,
                role_id=int(role.id),
                permission_id=permission_id,
                status="ACTIVE",
            ))

        version_before = int(role.version or 0)
        from app.services.data_scope_service import save_role_scope_in_session

        scope_change = save_role_scope_in_session(
            db,
            role,
            body.get("scopeCode"),
            target_json=(
                body["scopeTarget"]
                if "scopeTarget" in body
                else body.get("targetJson")
            ),
        )
        scope_before = scope_change["before"] or {
            "scopeCode": None,
            "scopeTarget": {},
            "version": None,
        }
        role.version = version_before + 1
        source.permission_codes_json = {"items": final_codes}
        source.drift_json = {
            **(source.drift_json or {}),
            "policy": "PINNED",
            "automaticUpgrade": False,
        }
        source.status = "ACTIVE"
        source.is_deleted = False

        added = sorted(set(final_codes) - existing_codes)
        removed = sorted(existing_codes - set(final_codes))
        digest = lambda values: hashlib.sha256(
            json.dumps(sorted(values), separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        high_risk = sorted(
            code for code in set(added) | set(removed)
            if str((permission_meta(code) or {}).get("riskLevel") or "").upper() in {"HIGH", "CRITICAL"}
        )
        affected_member_count = int(db.scalar(select(func.count(UserRole.id)).where(
            UserRole.tenant_id == tenant_id,
            UserRole.role_id == int(role.id),
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
        )) or 0)
        scope_after = {
            "scopeCode": scope_change["scopeCode"],
            "scopeTarget": scope_change["scopeTarget"],
            "version": scope_change["version"],
        }

        from app.services import audit_log

        audit_log.record_critical_in_session(
            db,
            "ROLE_PERMISSION_SAVE",
            f"role:{role.id}",
            detail={
                "roleCode": role.role_code,
                "roleVersionBefore": version_before,
                "roleVersionAfter": int(role.version or 0),
                "reason": reason,
                "requestId": request_id,
                "beforePermissionDigest": digest(existing_codes),
                "afterPermissionDigest": digest(final_codes),
                "addedPermissionCodes": added,
                "removedPermissionCodes": removed,
                "readOnlyPreservedPermissionCodes": sorted(preserved),
                "scopeBefore": scope_before,
                "scopeAfter": scope_after,
                "affectedMemberCount": affected_member_count,
                "highRiskPermissionCodes": high_risk,
                "moduleCode": "systemAdmin",
                "authoritySource": "ROLE_PERMISSION_PINNED",
            },
            tenant_id=tenant_id,
            resource_id=str(role.id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services.auth_service_db import invalidate_tenant_subject_caches

    cache_invalidated = True
    try:
        invalidate_tenant_subject_caches(tenant_id)
    except Exception:
        cache_invalidated = False
    return success({
        "id": str(role_id),
        "permissionCount": len(final_codes),
        "permissionCodes": final_codes,
        "version": version_before + 1,
        "scopeCode": scope_after["scopeCode"],
        "beforePermissionDigest": digest(existing_codes),
        "afterPermissionDigest": digest(final_codes),
        "addedPermissionCodes": added,
        "removedPermissionCodes": removed,
        "readOnlyPreservedPermissionCodes": sorted(preserved),
        "affectedMemberCount": affected_member_count,
        "highRiskPermissionCodes": high_risk,
        "cacheInvalidated": cache_invalidated,
    }, message="权限配置已生效；该角色成员需重新登录")


@_replacements.get("/system/export/role-config/{role_id}", summary="导出角色权限配置（真实 JSON，不含成员）")
def export_role_config(
    role_id: int,
    user=Depends(require_permission("systemAdmin.role.view")),
):
    """Export the same permission Authority consumed by runtime authorization."""
    from datetime import datetime

    from app.core.exceptions import AppException
    from app.models import Role

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(
            Role.id == int(role_id),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        )).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        codes = sorted(_runtime_role_permission_codes(db, role, tenant_id=tenant_id))
        payload = {
            "roleName": role.role_name,
            "roleCode": role.role_code,
            "roleType": "BUILTIN" if str(role.role_type or "").upper() == "SYSTEM" else "CUSTOM",
            "scopeCode": _bundle._role_scope(role),
            "permissionCount": len(codes),
            "permissions": codes,
            "permissionAuthority": (
                "PUBLISHED_ROLE_TEMPLATE"
                if str(role.role_type or "").upper() == "SYSTEM"
                else "ROLE_PERMISSION_PINNED"
            ),
            "exportedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return _bundle._json_response(
            payload,
            f"角色配置_{role.role_code}.json",
            user,
            f"角色配置「{role.role_name}」",
        )
    finally:
        db.close()


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


def __getattr__(name: str):
    """Keep direct-call compatibility for I4 adapters and legacy tests."""
    return getattr(_bundle, name)
