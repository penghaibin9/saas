"""SCHOOL_ADMIN wildcard-retirement runtime resolver.

This module is intentionally side-effect free.  The cutover card imports it from
``app.core.permissions`` only after the preflight gate proves that the latest
published SCHOOL_ADMIN TENANT RoleTemplate is an exact normalized snapshot of
the authoritative school-assignable Permission Catalog universe.

Security properties:
- PLATFORM/enterprise permissions can never enter the returned set;
- DB-enabled runtime fails closed on missing/drifted templates;
- DB-disabled compatibility returns the same explicit Catalog set, never ``*``;
- DENY rows or incomplete/extra ALLOW rows fail closed rather than widening.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.permission_catalog import load_permission_catalog

SCHOOL_ADMIN_ROLE_CODE = "SCHOOL_ADMIN"
PLATFORM_TENANT_ID = 0


def catalog_school_admin_permissions() -> tuple[str, ...]:
    """Return the canonical explicit school-assignable TENANT universe."""
    entries = load_permission_catalog().get("entries") or []
    codes = {
        str(item.get("permissionCode") or "").strip()
        for item in entries
        if str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and str(item.get("plane") or "").upper() == "TENANT"
        and bool(item.get("tenantAssignable"))
        and str(item.get("permissionCode") or "").strip()
    }
    forbidden = sorted(
        code for code in codes
        if code.startswith("platform.") or code.startswith("enterprise.")
    )
    if forbidden:
        raise RuntimeError(
            "SCHOOL_ADMIN catalog universe contains forbidden permission plane: "
            + ",".join(forbidden[:20])
        )
    return tuple(sorted(codes))


def _latest_published_school_admin_template(db):
    from app.models.permission_governance import (
        TEMPLATE_CATEGORY_SYSTEM_ROLE,
        TEMPLATE_PLANE_TENANT,
        TEMPLATE_PUBLISHED,
        RoleTemplate,
    )

    return db.scalars(select(RoleTemplate).where(
        RoleTemplate.tenant_id == PLATFORM_TENANT_ID,
        RoleTemplate.template_code == SCHOOL_ADMIN_ROLE_CODE,
        RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
        RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
        RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
        RoleTemplate.status == "ACTIVE",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(
        RoleTemplate.template_version.desc(),
        RoleTemplate.id.desc(),
    ).limit(1)).first()


def published_school_admin_permissions(db) -> tuple[str, ...]:
    """Read normalized latest-published template truth and require exact parity."""
    from app.models.permission_governance import (
        EFFECT_ALLOW,
        EFFECT_DENY,
        RoleTemplatePermission,
    )

    expected = set(catalog_school_admin_permissions())
    template = _latest_published_school_admin_template(db)
    if template is None:
        return ()

    rows = list(db.scalars(select(RoleTemplatePermission).where(
        RoleTemplatePermission.tenant_id == PLATFORM_TENANT_ID,
        RoleTemplatePermission.role_template_id == int(template.id),
        RoleTemplatePermission.is_deleted.is_(False),
    )).all())
    allowed = {row.permission_code for row in rows if row.effect == EFFECT_ALLOW}
    denied = {row.permission_code for row in rows if row.effect == EFFECT_DENY}
    if denied or allowed != expected:
        return ()
    if any(code.startswith("platform.") or code.startswith("enterprise.") for code in allowed):
        return ()
    return tuple(sorted(allowed))


def resolve_school_admin_permissions() -> tuple[str, ...]:
    """Resolve runtime SCHOOL_ADMIN permissions with a fail-closed DB cutover."""
    try:
        expected = catalog_school_admin_permissions()
    except Exception:
        return ()

    try:
        from app.db.session import db_enabled, get_sessionmaker

        if not db_enabled():
            # Unit/dev compatibility is still explicit and Catalog-governed.
            return expected

        db = get_sessionmaker()()
        try:
            return published_school_admin_permissions(db)
        finally:
            db.close()
    except Exception:
        return ()


def school_admin_cutover_preflight() -> dict:
    """Read-only proof used immediately before removing the legacy runtime wildcard."""
    from app.db.session import db_enabled, get_sessionmaker

    expected = set(catalog_school_admin_permissions())
    if not db_enabled():
        raise RuntimeError("SCHOOL_ADMIN retirement preflight requires DB_ENABLED=true")

    db = get_sessionmaker()()
    try:
        template = _latest_published_school_admin_template(db)
        actual = set(published_school_admin_permissions(db))
        if template is None:
            raise RuntimeError("missing published SCHOOL_ADMIN TENANT RoleTemplate")
        if actual != expected:
            raise RuntimeError(
                f"SCHOOL_ADMIN normalized snapshot drift expected={len(expected)} actual={len(actual)}"
            )
        return {
            "roleCode": SCHOOL_ADMIN_ROLE_CODE,
            "templateId": str(template.id),
            "templateVersion": int(template.template_version or 0),
            "explicitPermissionCount": len(actual),
            "tenantPermissionUniverseCount": len(expected),
            "exactSnapshot": True,
            "containsRuntimeWildcard": "*" in actual,
            "platformPermissionCount": sum(1 for code in actual if code.startswith("platform.")),
            "enterprisePermissionCount": sum(1 for code in actual if code.startswith("enterprise.")),
            "dbFailurePolicy": "FAIL_CLOSED",
            "dbDisabledCompatibility": "AUTHORITATIVE_CATALOG_EXPLICIT_SET",
        }
    finally:
        db.close()
