"""B8 SYSTEM-role shadow resolver and immutable TENANT template convergence.

The four resolver planes deliberately remain separate:
- OLD built-in ROLE_PERMISSIONS for delivered school roles;
- NEW latest published school-assignable TENANT RoleTemplate (normalized rows only);
- CUSTOM runtime RolePermission (never falls back to a template);
- PLATFORM workforce ROLE_PERMISSIONS, guarded by the PLATFORM permission plane.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.permission_catalog import load_permission_catalog
from app.core.permissions import ROLE_PERMISSIONS
from app.db.session import get_sessionmaker
from app.models import Permission, Role, RolePermission
from app.models.permission_governance import (
    EFFECT_ALLOW,
    EFFECT_DENY,
    TEMPLATE_CATEGORY_SYSTEM_ROLE,
    TEMPLATE_PLANE_TENANT,
    TEMPLATE_PUBLISHED,
    CustomRoleSource,
    RoleTemplate,
    RoleTemplatePermission,
)
from app.modules.system_admin.policies.role_template_plane import is_school_role_template_code

PLATFORM_TENANT = 0
SHADOW_CLASS_ALLOW_ALLOW = "ALLOW_ALLOW"
SHADOW_CLASS_DENY_DENY = "DENY_DENY"
SHADOW_CLASS_ALLOW_DENY = "ALLOW_DENY"
SHADOW_CLASS_DENY_ALLOW = "DENY_ALLOW"


def _digest(codes: Iterable[str]) -> str:
    payload = json.dumps(sorted(set(codes)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def active_tenant_permission_codes() -> tuple[str, ...]:
    """B8 school-template universe: ACTIVE + TENANT + tenantAssignable only.

    Enterprise Portal permissions are TENANT-plane but explicitly
    tenantAssignable=false; they must never enter a school RoleTemplate.
    """
    entries = load_permission_catalog().get("entries") or []
    codes = {
        str(item.get("permissionCode") or "").strip()
        for item in entries
        if str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and str(item.get("plane") or "").upper() == "TENANT"
        and bool(item.get("tenantAssignable"))
        and str(item.get("permissionCode") or "").strip()
    }
    forbidden = sorted(code for code in codes if code.startswith("platform.") or code.startswith("enterprise."))
    if forbidden:
        raise AppException(
            "B8_PERMISSION_PLANE_DRIFT",
            "学校 RoleTemplate 权限 universe 混入平台或企业权限",
            http_status=409,
            details={"permissionCodes": forbidden[:50]},
        )
    return tuple(sorted(codes))


def _match(code: str, patterns: Iterable[str]) -> bool:
    for raw in patterns:
        pattern = str(raw or "").strip()
        if pattern == "*" or code == pattern:
            return True
        if pattern.endswith(".*") and (code == pattern[:-2] or code.startswith(pattern[:-1])):
            return True
        if pattern.startswith("*.") and code.endswith(pattern[1:]):
            return True
    return False


def delivered_system_role_codes() -> tuple[str, ...]:
    return tuple(sorted(role_code for role_code in ROLE_PERMISSIONS if is_school_role_template_code(role_code)))


def old_builtin_allows(role_code: str, permission_code: str) -> bool:
    code = str(permission_code or "").strip()
    if code not in set(active_tenant_permission_codes()):
        return False
    return _match(code, ROLE_PERMISSIONS.get(str(role_code or "").strip(), set()))


def expected_system_role_permissions(role_code: str) -> tuple[str, ...]:
    universe = active_tenant_permission_codes()
    patterns = ROLE_PERMISSIONS.get(str(role_code or "").strip(), set())
    return tuple(code for code in universe if _match(code, patterns))


def _latest_published_template(db, role_code: str) -> RoleTemplate | None:
    return db.scalars(select(RoleTemplate).where(
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.template_code == str(role_code),
        RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
        RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
        RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
        RoleTemplate.status == "ACTIVE",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()


def _normalized_template_permissions(db, template: RoleTemplate | None) -> tuple[set[str], set[str]]:
    if template is None:
        return set(), set()
    rows = list(db.scalars(select(RoleTemplatePermission).where(
        RoleTemplatePermission.tenant_id == PLATFORM_TENANT,
        RoleTemplatePermission.role_template_id == int(template.id),
        RoleTemplatePermission.is_deleted.is_(False),
    )).all())
    allowed = {row.permission_code for row in rows if row.effect == EFFECT_ALLOW}
    denied = {row.permission_code for row in rows if row.effect == EFFECT_DENY}
    return allowed, denied


def published_template_allows(db, role_code: str, permission_code: str) -> bool:
    template = _latest_published_template(db, role_code)
    allowed, denied = _normalized_template_permissions(db, template)
    code = str(permission_code or "").strip()
    return code in allowed and code not in denied


def custom_role_permission_codes(db, *, tenant_id: int, role_id: int) -> tuple[str, ...]:
    role = db.scalars(select(Role).where(
        Role.tenant_id == int(tenant_id),
        Role.id == int(role_id),
        Role.role_type == "CUSTOM",
        Role.status == "ACTIVE",
        Role.is_deleted.is_(False),
    )).first()
    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == int(tenant_id),
        CustomRoleSource.role_id == int(role_id),
        CustomRoleSource.is_deleted.is_(False),
    )).first()
    if role is None or source is None or source.role_code != role.role_code:
        raise AppException(
            "CUSTOM_ROLE_BINDING_DRIFT",
            "CUSTOM resolver 缺少稳定 Role ↔ CustomRoleSource 绑定",
            http_status=409,
            details={"tenantId": int(tenant_id), "roleId": int(role_id)},
        )
    codes = list(db.scalars(select(Permission.permission_code).join(
        RolePermission, RolePermission.permission_id == Permission.id,
    ).where(
        RolePermission.tenant_id == int(tenant_id),
        RolePermission.role_id == int(role_id),
        RolePermission.status == "ACTIVE",
        RolePermission.is_deleted.is_(False),
    )).all())
    return tuple(sorted(set(codes)))


def custom_role_allows(db, *, tenant_id: int, role_id: int, permission_code: str) -> bool:
    return str(permission_code or "").strip() in set(custom_role_permission_codes(db, tenant_id=tenant_id, role_id=role_id))


def platform_workforce_allows(role_code: str, permission_code: str) -> bool:
    role = str(role_code or "").strip().upper()
    code = str(permission_code or "").strip()
    if not role.startswith("PLATFORM_") or not code.startswith("platform."):
        return False
    return _match(code, ROLE_PERMISSIONS.get(role, set()))


def converge_published_system_templates(*, actor_user_id: int | None, source_commit_sha: str) -> dict:
    """Publish immutable school-assignable TENANT snapshots; never edit a published version."""
    from app.services import audit_log

    source_sha = str(source_commit_sha or "").strip()
    if len(source_sha) < 7:
        raise AppException("VALIDATION_ERROR", "B8 template convergence requires source commit SHA")
    now = datetime.utcnow()
    created: list[dict] = []
    unchanged: list[str] = []
    universe = set(active_tenant_permission_codes())
    db = get_sessionmaker()()
    try:
        for role_code in delivered_system_role_codes():
            expected = set(expected_system_role_permissions(role_code))
            forbidden = sorted(code for code in expected if code not in universe or code.startswith("platform.") or code.startswith("enterprise."))
            if forbidden:
                raise AppException(
                    "B8_PERMISSION_PLANE_DRIFT",
                    "学校 RoleTemplate 展开越过学校可分配 TENANT permission universe",
                    http_status=409,
                    details={"roleCode": role_code, "permissionCodes": forbidden[:50]},
                )
            latest = _latest_published_template(db, role_code)
            current_allow, current_deny = _normalized_template_permissions(db, latest)
            if latest is not None and current_allow == expected and not current_deny:
                unchanged.append(role_code)
                continue
            latest_any = db.scalars(select(RoleTemplate).where(
                RoleTemplate.tenant_id == PLATFORM_TENANT,
                RoleTemplate.template_code == role_code,
                RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
                RoleTemplate.template_category == TEMPLATE_CATEGORY_SYSTEM_ROLE,
                RoleTemplate.is_deleted.is_(False),
            ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
            next_version = int(latest_any.template_version or 0) + 1 if latest_any is not None else 1
            wildcard_patterns = sorted(
                pattern for pattern in ROLE_PERMISSIONS.get(role_code, set())
                if pattern == "*" or pattern.endswith(".*") or pattern.startswith("*.")
            )
            template = RoleTemplate(
                tenant_id=PLATFORM_TENANT,
                template_code=role_code,
                template_name=latest_any.template_name if latest_any is not None else role_code,
                template_version=next_version,
                template_plane=TEMPLATE_PLANE_TENANT,
                template_category=TEMPLATE_CATEGORY_SYSTEM_ROLE,
                publish_status=TEMPLATE_PUBLISHED,
                permission_digest=_digest(expected),
                previous_template_id=int(latest_any.id) if latest_any is not None else None,
                change_reason="B8 SYSTEM shadow: explicit school-assignable TENANT permission snapshot",
                source_commit_sha=source_sha,
                effective_at=now,
                published_at=now,
                published_by=actor_user_id,
                delivered=True,
                bundle_codes_json={"items": []},
                permission_ceiling_json={"items": sorted(expected), "permissionDigest": _digest(expected), "compatibilityOnly": True},
                wildcard_json={"sourcePatterns": wildcard_patterns, "runtimeRetired": False, "b8ShadowOnly": True} if wildcard_patterns else None,
                status="ACTIVE",
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            db.add(template)
            db.flush()
            for code in sorted(expected):
                db.add(RoleTemplatePermission(
                    tenant_id=PLATFORM_TENANT,
                    role_template_id=int(template.id),
                    permission_code=code,
                    effect=EFFECT_ALLOW,
                    created_by=actor_user_id,
                    updated_by=actor_user_id,
                ))
            audit_log.record_critical_in_session(
                db,
                "ROLE_TEMPLATE_PUBLISH",
                f"role-template:{role_code}:v{next_version}",
                tenant_id=PLATFORM_TENANT,
                resource_id=str(template.id),
                detail={
                    "reason": "B8_SYSTEM_SHADOW_CONVERGENCE",
                    "sourceCommitSha": source_sha,
                    "permissionDigest": template.permission_digest,
                    "permissionCount": len(expected),
                    "wildcardRuntimeRetired": False,
                },
            )
            created.append({
                "roleCode": role_code,
                "templateId": str(template.id),
                "templateVersion": next_version,
                "permissionCount": len(expected),
                "permissionDigest": template.permission_digest,
            })
        db.commit()
        return {
            "created": created,
            "createdCount": len(created),
            "unchangedRoleCodes": unchanged,
            "tenantPermissionUniverseCount": len(universe),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def shadow_system_roles() -> dict:
    universe = active_tenant_permission_codes()
    universe_set = set(universe)
    db = get_sessionmaker()()
    try:
        comparisons: list[dict] = []
        role_summaries: list[dict] = []
        plane_violations: list[dict] = []
        unexplained: list[dict] = []
        for role_code in delivered_system_role_codes():
            template = _latest_published_template(db, role_code)
            allowed, denied = _normalized_template_permissions(db, template)
            invalid = sorted(code for code in allowed | denied if code not in universe_set or code.startswith("platform.") or code.startswith("enterprise."))
            if invalid:
                plane_violations.append({"roleCode": role_code, "permissionCodes": invalid})
            counts = {
                SHADOW_CLASS_ALLOW_ALLOW: 0,
                SHADOW_CLASS_DENY_DENY: 0,
                SHADOW_CLASS_ALLOW_DENY: 0,
                SHADOW_CLASS_DENY_ALLOW: 0,
            }
            role_mismatches = 0
            for code in universe:
                old_allow = _match(code, ROLE_PERMISSIONS.get(role_code, set()))
                new_allow = code in allowed and code not in denied
                if old_allow and new_allow:
                    classification = SHADOW_CLASS_ALLOW_ALLOW
                elif not old_allow and not new_allow:
                    classification = SHADOW_CLASS_DENY_DENY
                elif old_allow:
                    classification = SHADOW_CLASS_ALLOW_DENY
                else:
                    classification = SHADOW_CLASS_DENY_ALLOW
                counts[classification] += 1
                if classification in (SHADOW_CLASS_ALLOW_DENY, SHADOW_CLASS_DENY_ALLOW):
                    row = {"roleCode": role_code, "permissionCode": code, "classification": classification, "explained": False, "explanation": ""}
                    comparisons.append(row)
                    unexplained.append(row)
                    role_mismatches += 1
            if template is None:
                missing = {
                    "roleCode": role_code,
                    "permissionCode": "<published-template>",
                    "classification": SHADOW_CLASS_ALLOW_DENY,
                    "explained": False,
                    "explanation": "MISSING_PUBLISHED_TENANT_TEMPLATE",
                }
                comparisons.append(missing)
                unexplained.append(missing)
                role_mismatches += 1
            role_summaries.append({
                "roleCode": role_code,
                "templateId": str(template.id) if template is not None else None,
                "templateVersion": int(template.template_version or 0) if template is not None else None,
                "normalizedPermissionCount": len(allowed),
                "mismatchCount": role_mismatches,
                "classifications": counts,
            })
        return {
            "resolverSet": ["OLD_BUILTIN_ROLE_PERMISSIONS", "NEW_PUBLISHED_TENANT_ROLE_TEMPLATE", "CUSTOM_ROLE_PERMISSION", "PLATFORM_WORKFORCE"],
            "shadowScope": "TENANT_SYSTEM_ROLES_ONLY",
            "schoolAssignableTenantOnly": True,
            "tenantPermissionUniverseCount": len(universe),
            "roleCount": len(role_summaries),
            "roles": role_summaries,
            "mismatches": comparisons,
            "unexplainedDriftCount": len(unexplained),
            "planeViolations": plane_violations,
            "planeViolationCount": len(plane_violations),
            "zeroUnexplainedDrift": not unexplained and not plane_violations,
            "customFallsBackToTemplate": False,
            "platformEntersSchoolTemplate": False,
            "enterpriseEntersSchoolTemplate": False,
        }
    finally:
        db.close()
