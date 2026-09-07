"""Canonical school role-assignment mutation with durable/cache split.

The existing System router already has the correct target-role Authority checks,
but it committed membership and then invalidated the subject cache without a
receipt. A cache outage could therefore make a committed role assignment look
like a failed request. This service keeps the same authorization/scope rules in
one transaction and performs cache invalidation strictly after commit.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker


def assign_user_roles(user_id: int, body: dict, *, user: dict | None = None) -> dict:
    from app.core.permissions import assert_delegable_permission_codes
    from app.models import Role, User, UserRole
    from app.modules.system_admin.routers import system_bundle as bundle
    from app.modules.system_admin.routers import system_router as canonical
    from app.services import audit_log
    from app.services.system_mutation_receipt_service import (
        _audit_cache_degraded,
        _optional_version,
        _subject_cache_receipt,
    )

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)

    payload = dict(body or {})
    codes = sorted({
        str(code).strip().upper()
        for code in (payload.get("roleCodes") or [])
        if str(code).strip()
    })
    if not codes:
        raise AppException("VALIDATION_ERROR", "至少保留一个角色", http_status=422)

    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        ).with_for_update()).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在", http_status=404)

        version_before = int(account.version or 0)
        _, occ = _optional_version(
            payload.get("expectedVersion"),
            current=version_before,
            label="账号角色",
        )

        if bundle._account_type_of(account, db) == "STUDENT":
            if codes != ["STUDENT"]:
                raise AppException(
                    "NO_PERMISSION",
                    "学生账号固定绑定 STUDENT，禁止分配教职工或管理员角色",
                    http_status=403,
                )
        elif "STUDENT" in codes:
            raise AppException("VALIDATION_ERROR", "教职工账号不能绑定 STUDENT 角色", http_status=422)

        if "SCHOOL_ADMIN" not in codes and bundle._is_last_active_school_admin(
            db, tenant_id, int(account.id)
        ):
            raise AppException(
                "VALIDATION_ERROR",
                "不能移除本校最后一名启用中的学校管理员",
                http_status=422,
            )

        roles = list(db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(codes),
            Role.status.in_(("ACTIVE", "ENABLED")),
            Role.is_deleted.is_(False),
        )).all())
        if len(roles) != len(codes):
            raise AppException("VALIDATION_ERROR", "包含不存在或已停用的角色", http_status=422)

        for role_obj in roles:
            patterns = canonical._runtime_role_permission_codes(
                db, role_obj, tenant_id=tenant_id,
            )
            try:
                assert_delegable_permission_codes(user or {}, patterns)
            except AppException as exc:
                if exc.code == "NO_PERMISSION":
                    raise AppException(
                        "NO_PERMISSION",
                        f"不能分配超出自身基础权限边界的角色：{role_obj.role_name}",
                        http_status=403,
                    ) from None
                raise

        existing_links = list(db.scalars(select(UserRole).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == int(account.id),
        ).with_for_update()).all())
        existing = {int(link.role_id): link for link in existing_links}
        before_codes = sorted({
            str(role.role_code)
            for role in db.scalars(select(Role).join(
                UserRole, UserRole.role_id == Role.id,
            ).where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == int(account.id),
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
                Role.is_deleted.is_(False),
            )).all()
        })

        wanted = {int(role_obj.id) for role_obj in roles}
        for role_id, link in existing.items():
            desired_active = role_id in wanted
            changed = (
                bool(link.is_deleted) == desired_active
                or (str(link.status or "").upper() == "ACTIVE") != desired_active
            )
            if desired_active:
                link.status = "ACTIVE"
                link.is_deleted = False
            else:
                link.status = "DISABLED"
                link.is_deleted = True
            if changed:
                link.version = int(link.version or 0) + 1

        for role_id in wanted - set(existing):
            link = UserRole(
                tenant_id=tenant_id,
                user_id=int(account.id),
                role_id=role_id,
                status="ACTIVE",
            )
            db.add(link)
            db.flush()
            existing[role_id] = link

        scope_result = []
        if "roleAssignments" in payload:
            from app.services.role_assignment_scope_service import sync_assignment_scopes

            scope_result = sync_assignment_scopes(
                db,
                account=account,
                roles=roles,
                links_by_role_id=existing,
                raw_assignments=payload.get("roleAssignments"),
                actor=user or {},
            )
        else:
            from app.services.role_assignment_scope_service import revoke_removed_role_scopes

            revoke_removed_role_scopes(
                db,
                tenant_id=tenant_id,
                user_id=int(account.id),
                active_role_codes=set(codes),
                actor=user or {},
            )

        account.version = version_before + 1
        version_after = int(account.version)
        audit_log.record_critical_in_session(
            db,
            "USER_ROLE_ASSIGN",
            f"user:{account.id}",
            detail={
                "loginName": account.login_name,
                "beforeRoleCodes": before_codes,
                "roleCodes": codes,
                "roleAssignments": scope_result,
                "expectedVersion": payload.get("expectedVersion"),
                "versionBefore": version_before,
                "versionAfter": version_after,
                "optimisticLockEnforced": occ,
                "moduleCode": "systemAdmin",
                "authoritySource": "PUBLISHED_ROLE_TEMPLATE_OR_CUSTOM_ROLE_PERMISSION",
            },
            tenant_id=tenant_id,
            resource_id=str(account.id),
        )
        db.commit()
        login_name = str(account.login_name or "")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    cache = _subject_cache_receipt(int(user_id), tenant_id)
    _audit_cache_degraded(
        "USER_ROLE_ASSIGN",
        f"user:{user_id}",
        tenant_id,
        cache,
        {
            "userId": str(user_id),
            "loginName": login_name,
            "roleCodes": codes,
            "version": version_after,
        },
    )
    return {
        "id": str(user_id),
        "roleCodes": codes,
        "roleAssignments": scope_result,
        "version": version_after,
        "runtimeMaterialized": True,
        "optimisticLockEnforced": occ,
        **cache,
    }
