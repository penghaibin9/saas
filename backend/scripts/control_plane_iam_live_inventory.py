"""Read-only W0/W8 inventory for the currently configured MySQL database."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, inspect, select

from app.core.permission_catalog import load_permission_catalog
from app.db.session import get_engine, get_sessionmaker
from app.models import Permission, Role, RolePermission
from app.models.permission_governance import CustomRoleSource, RoleTemplate, RoleTemplatePermission
from app.services.system_role_shadow_service import shadow_system_roles


def _digest(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    engine = get_engine()
    table_names = set(inspect(engine).get_table_names())
    required = {
        "t_permission", "t_role", "t_role_permission", "t_role_template",
        "t_role_template_permission", "t_custom_role_source",
    }
    missing = sorted(required - table_names)
    if missing:
        print(json.dumps({"databaseReady": False, "missingTables": missing}, ensure_ascii=False, indent=2))
        return

    catalog_entries = list(load_permission_catalog().get("entries") or [])
    canonical_assignable = {
        str(item["permissionCode"])
        for item in catalog_entries
        if item.get("plane") == "TENANT"
        and str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and item.get("tenantAssignable")
        and item.get("customRoleAssignable")
        and not str(item.get("permissionCode") or "").startswith(("system.", "platform.", "enterprise."))
    }

    db = get_sessionmaker()()
    try:
        templates = list(db.scalars(select(RoleTemplate).where(RoleTemplate.is_deleted.is_(False)).order_by(
            RoleTemplate.template_plane, RoleTemplate.template_code, RoleTemplate.template_version
        )).all())
        template_rows = [
            {
                "id": str(row.id),
                "templateCode": row.template_code,
                "templateVersion": int(row.template_version or 0),
                "templatePlane": row.template_plane,
                "templateCategory": row.template_category,
                "publishStatus": row.publish_status,
                "permissionDigest": row.permission_digest,
                "version": int(row.version or 0),
            }
            for row in templates
        ]
        legacy_permission_rows = int(db.scalar(select(func.count(Permission.id)).where(
            Permission.permission_code.like("system.%")
        )) or 0)
        legacy_role_links = int(db.scalar(select(func.count(RolePermission.id)).join(
            Permission, Permission.id == RolePermission.permission_id
        ).where(
            Permission.permission_code.like("system.%"),
            RolePermission.is_deleted.is_(False),
            RolePermission.status == "ACTIVE",
        )) or 0)
        legacy_template_links = int(db.scalar(select(func.count(RoleTemplatePermission.id)).where(
            RoleTemplatePermission.permission_code.like("system.%"),
            RoleTemplatePermission.is_deleted.is_(False),
        )) or 0)
        custom_codes = set(db.scalars(select(Permission.permission_code).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).join(Role, Role.id == RolePermission.role_id).where(
            Role.role_type == "CUSTOM",
            Role.is_deleted.is_(False),
            RolePermission.is_deleted.is_(False),
            RolePermission.status == "ACTIVE",
        )).all())
        outside = sorted(custom_codes - canonical_assignable)
        shadow = shadow_system_roles()
        payload = {
            "databaseReady": True,
            "roleTemplateCount": len(template_rows),
            "roleTemplateDigest": _digest(template_rows),
            "roleTemplates": template_rows,
            "customRoleSourceCount": int(db.scalar(select(func.count(CustomRoleSource.id)).where(
                CustomRoleSource.is_deleted.is_(False)
            )) or 0),
            "customRolePermissionCodeCount": len(custom_codes),
            "customRoleOutsideAuthoringCodes": outside,
            "customRoleOutsideAuthoringCount": len(outside),
            "legacySystemReferences": {
                "permissionRows": legacy_permission_rows,
                "activeRolePermissionLinks": legacy_role_links,
                "roleTemplatePermissionLinks": legacy_template_links,
            },
            "systemShadow": {
                "roleCount": shadow.get("roleCount"),
                "unexplainedDriftCount": shadow.get("unexplainedDriftCount"),
                "planeViolationCount": shadow.get("planeViolationCount"),
                "zeroUnexplainedDrift": shadow.get("zeroUnexplainedDrift"),
                "mismatches": shadow.get("mismatches"),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
