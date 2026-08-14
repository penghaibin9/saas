"""Canonical CUSTOM RolePermission materialization command boundary."""
from __future__ import annotations

from sqlalchemy import select


def _validated_codes(raw_codes) -> set[str]:
    from app.core.exceptions import AppException

    codes = {str(code or "").strip() for code in (raw_codes or []) if str(code or "").strip()}
    invalid = sorted(c for c in codes if c == "*" or c.endswith(".*") or c.startswith("*.") or c.startswith("platform."))
    if invalid:
        raise AppException(
            "PERMISSION_CATALOG_DRIFT",
            "自定义学校角色只能物化具体 TENANT permissionCode",
            http_status=409,
            details={"invalidPermissionCodes": invalid[:50]},
        )
    return codes


def materialize_custom_role_source(db, tenant_id: int, role_code: str) -> dict:
    """Make RolePermission equal CustomRoleSource in the caller's transaction.

    This function never commits and never creates global Permission rows.
    """
    from app.core.exceptions import AppException
    from app.models import Permission, Role, RolePermission
    from app.models.permission_governance import CustomRoleSource

    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tenant_id,
        CustomRoleSource.role_code == role_code,
        CustomRoleSource.is_deleted.is_(False),
    ).with_for_update()).first()
    if source is None:
        raise AppException("CUSTOM_ROLE_SOURCE_MISSING", f"自定义角色治理源不存在：{role_code}", http_status=409)

    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == role_code,
        Role.role_type == "CUSTOM",
        Role.is_deleted.is_(False),
    ).with_for_update()).first()
    if role is None:
        raise AppException(
            "CUSTOM_ROLE_RUNTIME_MISSING",
            f"治理角色 {role_code} 尚未绑定 runtime Role，拒绝假激活",
            http_status=409,
        )

    desired = _validated_codes((source.permission_codes_json or {}).get("items") or [])
    permissions = {
        row.permission_code: row
        for row in db.scalars(select(Permission).where(Permission.permission_code.in_(sorted(desired)))).all()
    } if desired else {}
    missing = sorted(desired - set(permissions))
    if missing:
        raise AppException(
            "PERMISSION_CATALOG_DRIFT",
            "安全变更包含尚未由 Catalog/Reconciliation 创建的权限，拒绝激活",
            http_status=409,
            details={"missingPermissionCodes": missing[:50], "missingCount": len(missing)},
        )

    links = list(db.scalars(select(RolePermission).where(
        RolePermission.tenant_id == tenant_id,
        RolePermission.role_id == role.id,
    ).with_for_update()).all())
    by_permission_id = {int(link.permission_id): link for link in links}
    desired_ids = {int(permissions[code].id) for code in desired}

    for permission_id, link in by_permission_id.items():
        if permission_id in desired_ids:
            link.status = "ACTIVE"
            link.is_deleted = False
        else:
            link.status = "DISABLED"
            link.is_deleted = True

    for code in sorted(desired):
        permission_id = int(permissions[code].id)
        if permission_id not in by_permission_id:
            db.add(RolePermission(
                tenant_id=tenant_id,
                role_id=int(role.id),
                permission_id=permission_id,
                status="ACTIVE",
            ))

    role.version = int(role.version or 0) + 1
    return {
        "roleId": str(role.id),
        "roleCode": role.role_code,
        "permissionCount": len(desired),
        "roleVersion": int(role.version or 0),
    }
