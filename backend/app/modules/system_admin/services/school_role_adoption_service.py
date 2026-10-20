"""Pin a delivered business role locally without replacing its runtime identity."""
from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.permissions import assert_delegable_permission_codes
from app.models import CustomRoleSource, Permission, Role, RolePermission
from app.services import audit_log, system_role_shadow_service as shadow
from app.services.saas_role_templates import ROLE_TEMPLATE_BY_CODE


def is_adoptable_code(code: str) -> bool:
    template = ROLE_TEMPLATE_BY_CODE.get(code, {})
    return bool(template.get("teacherAssignable")) or code == "STAFF"


def has_local_adoption(db, role, tenant_id: int) -> bool:
    """Reserved codes remain reserved except for the explicit adoption command."""
    if not is_adoptable_code(role.role_code):
        return False
    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tenant_id,
        CustomRoleSource.role_id == role.id,
        CustomRoleSource.role_code == role.role_code,
        CustomRoleSource.is_deleted.is_(False),
    )).first()
    return bool(source and source.source_template_code == role.role_code
                and source.source_template_version > 0
                and (source.drift_json or {}).get("origin") == "SCHOOL_ADOPTED_SYSTEM_ROLE"
                and (source.drift_json or {}).get("automaticUpgrade") is False)


def adoption_preview(db, role) -> dict:
    if role.role_type != "SYSTEM" or not is_adoptable_code(role.role_code):
        return {"eligible": False}
    template = shadow._latest_published_template(db, role.role_code)
    codes = shadow.published_system_role_permissions(db, role.role_code)
    return {"eligible": True, "expectedVersion": int(role.version or 0),
            "expectedTemplateVersion": template.template_version,
            "expectedTemplateDigest": shadow._digest(codes), "permissionCount": len(codes)}


def adopt_in_session(db, *, tenant_id: int, role_id: int, body: dict, actor: dict) -> dict:
    """Caller owns commit/rollback; membership and scope rows are never rewritten."""
    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id, Role.id == role_id,
        Role.is_deleted.is_(False),
    ).with_for_update()).first()
    if role is None:
        raise AppException("DATA_NOT_FOUND", "角色不存在")
    if role.role_type != "SYSTEM" or not is_adoptable_code(role.role_code):
        raise AppException("VALIDATION_ERROR", "此角色不能转为本校维护", http_status=422)
    preview = adoption_preview(db, role)
    if any(str(body.get(key)) != str(preview[key]) for key in (
        "expectedVersion", "expectedTemplateVersion", "expectedTemplateDigest",
    )):
        raise AppException("DATA_CONFLICT", "角色或模板已变化，请重新读取后核对", http_status=409)
    codes = set(shadow.published_system_role_permissions(db, role.role_code))
    # Pinning must not launder temporary delegation into permanent role authority.
    assert_delegable_permission_codes(actor, codes | {"systemAdmin.role.config"})
    existing_source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tenant_id, CustomRoleSource.role_id == role_id,
    ).with_for_update()).first()
    if existing_source is not None:
        raise AppException("CUSTOM_ROLE_BINDING_DRIFT", "角色已有本校维护记录，请核对后再处理", http_status=409)
    permissions = list(db.scalars(select(Permission).where(
        Permission.permission_code.in_(codes),
    )).all()) if codes else []
    if {p.permission_code for p in permissions} != codes:
        raise AppException("PERMISSION_CATALOG_DRIFT", "权限目录尚未完成同步，不能转换角色", http_status=409)
    links = list(db.scalars(select(RolePermission).where(
        RolePermission.tenant_id == tenant_id, RolePermission.role_id == role_id,
    )).all())
    wanted = {p.id for p in permissions}
    existing = {link.permission_id for link in links}
    # Old SYSTEM links were not authority. Reconcile all of them to the snapshot,
    # including stale grants, before switching the resolver to CUSTOM.
    for link in links:
        link.status = "ACTIVE" if link.permission_id in wanted else "DISABLED"
        link.is_deleted = link.permission_id not in wanted
    for permission_id in wanted - existing:
        db.add(RolePermission(tenant_id=tenant_id, role_id=role_id,
                              permission_id=permission_id, status="ACTIVE"))
    db.add(CustomRoleSource(
        tenant_id=tenant_id, role_id=role_id, role_code=role.role_code,
        source_template_code=role.role_code,
        source_template_version=preview["expectedTemplateVersion"],
        permission_codes_json={"items": sorted(codes)},
        drift_json={"origin": "SCHOOL_ADOPTED_SYSTEM_ROLE", "policy": "PINNED",
                    "automaticUpgrade": False, "adoptedDigest": preview["expectedTemplateDigest"]},
        status="ACTIVE",
    ))
    role.role_type = "CUSTOM"
    role.version = preview["expectedVersion"] + 1
    audit_log.record_critical_in_session(
        db, "ROLE_ADOPT", f"role:{role_id}", tenant_id=tenant_id, resource_id=str(role_id),
        detail={"roleCode": role.role_code, "reason": body["reason"], "requestId": body["requestId"],
                "roleVersionBefore": preview["expectedVersion"], "roleVersionAfter": role.version,
                "sourceTemplateVersion": preview["expectedTemplateVersion"],
                "beforePermissionDigest": preview["expectedTemplateDigest"],
                "afterPermissionDigest": preview["expectedTemplateDigest"],
                "addedPermissionCodes": [], "removedPermissionCodes": [],
                "moduleCode": "systemAdmin"},
    )
    return {"id": str(role_id), "version": role.version, "permissionCount": len(codes),
            "type": "CUSTOM", "automaticUpgrade": False}
