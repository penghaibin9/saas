"""B7 School IAM Workspace projection, provenance, drift and Access Explain."""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.effective_access import explain_tenant_access
from app.core.exceptions import AppException
from app.core.permission_catalog import load_permission_catalog, permission_meta
from app.db.session import get_sessionmaker
from app.models import Permission, Role, RolePermission, User, UserRole
from app.models.permission_governance import CustomRoleSource, RoleTemplate
from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code

PLATFORM_TENANT = 0
PUBLISHED_TEMPLATE_STATUSES = ("ACTIVE", "PUBLISHED")


def _tenant_id() -> int:
    tid = int(current_tenant_id() or 0)
    if tid <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "学校 IAM 工作区缺少租户上下文", http_status=403)
    return tid


def _json_items(value) -> list[str]:
    if isinstance(value, dict):
        value = value.get("items") or []
    if not isinstance(value, (list, tuple, set)):
        return []
    return sorted({str(item or "").strip() for item in value if str(item or "").strip()})


def _template_permissions(item: RoleTemplate | None) -> list[str]:
    if item is None:
        return []
    return _json_items(item.permission_ceiling_json or {})


def _latest_template(db, template_code: str) -> RoleTemplate | None:
    return db.scalar(select(RoleTemplate).where(
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.template_code == template_code,
        RoleTemplate.status.in_(PUBLISHED_TEMPLATE_STATUSES),
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_version.desc()).limit(1))


def _template_version(db, template_code: str, template_version: int) -> RoleTemplate | None:
    return db.scalar(select(RoleTemplate).where(
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.template_code == template_code,
        RoleTemplate.template_version == int(template_version),
        RoleTemplate.is_deleted.is_(False),
    ).limit(1))


def assignable_catalog() -> dict:
    catalog = load_permission_catalog()
    entries = [
        item for item in (catalog.get("entries") or [])
        if item.get("plane") == "TENANT"
        and bool(item.get("tenantAssignable"))
        and str(item.get("lifecycle") or "").upper() == "ACTIVE"
    ]
    custom = [item for item in entries if bool(item.get("customRoleAssignable"))]
    internship_recruitment = [item for item in custom if str(item.get("permissionCode") or "").startswith("internship.recruitment.")]
    return {
        "assignablePermissions": entries,
        "customRoleAssignablePermissions": custom,
        "internshipRecruitmentPermissions": internship_recruitment,
        "enterprisePermissionsVisibleButSchoolAssignable": False,
        "enterprisePermissionCount": sum(1 for code in catalog.get("_byCode", {}) if str(code).startswith("enterprise.internship.")),
    }


def template_catalog() -> list[dict]:
    tid = _tenant_id()
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.status.in_(PUBLISHED_TEMPLATE_STATUSES),
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_code, RoleTemplate.template_version.desc())).all())
        sources = list(db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tid,
            CustomRoleSource.is_deleted.is_(False),
        )).all())
        pinned_by_code = Counter(str(item.source_template_code or "") for item in sources)
        pinned_versions: dict[str, set[int]] = defaultdict(set)
        for source in sources:
            pinned_versions[str(source.source_template_code or "")].add(int(source.source_template_version or 0))

        seen = set()
        result = []
        for item in rows:
            if item.template_code in seen:
                continue
            seen.add(item.template_code)
            if str(item.template_code or "").upper().startswith("PLATFORM_") or str(item.template_code or "").upper() in {"COMPANY_ADMIN", "HR", "MENTOR"}:
                continue
            ceiling = dict(item.permission_ceiling_json or {})
            result.append({
                "id": str(item.id),
                "templateCode": item.template_code,
                "templateName": item.template_name,
                "templateVersion": int(item.template_version or 0),
                "permissionDigest": ceiling.get("permissionDigest"),
                "permissions": _template_permissions(item),
                "immutable": True,
                "customRoleUpgradePolicy": "DERIVED_PINNED",
                "schoolPinnedCustomRoleCount": int(pinned_by_code.get(item.template_code, 0)),
                "schoolPinnedSourceVersions": sorted(pinned_versions.get(item.template_code, set())),
            })
        return result
    finally:
        db.close()


def _role_permissions(db, tenant_id: int, role: Role) -> list[str]:
    role_type = str(role.role_type or "SYSTEM").upper()
    if role_type == "CUSTOM":
        return sorted(set(db.scalars(select(Permission.permission_code).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
        )).all()))
    from app.core.permissions import ROLE_PERMISSIONS
    return sorted(set(ROLE_PERMISSIONS.get(role.role_code, set())))


def _system_role_governance(role: Role, runtime_permissions: list[str]) -> dict:
    wildcards = sorted(code for code in runtime_permissions if code == "*" or code.endswith(".*"))
    return {
        "templateProvenance": {
            "authority": "ROLE_PERMISSIONS_LEGACY",
            "provenanceStatus": "LEGACY_SYSTEM_ROLE",
            "roleVersion": int(role.version or 0),
            "upgradePolicy": "B8_SHADOW_THEN_RETIRE",
        },
        "drift": {
            "detected": False,
            "notApplicableReason": "SYSTEM_ROLE_STILL_READS_ROLE_PERMISSIONS",
            "wildcards": wildcards,
            "b8RetirementPending": bool(wildcards),
        },
        "templateImpact": {
            "automaticUpgrade": False,
            "status": "NOT_APPLICABLE_UNTIL_SYSTEM_SHADOW",
            "wouldAdd": [],
            "wouldRemove": [],
        },
    }


def _custom_role_governance(db, tenant_id: int, role: Role, runtime_permissions: list[str]) -> dict:
    runtime = set(runtime_permissions)
    source = db.scalar(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tenant_id,
        CustomRoleSource.role_code == role.role_code,
        CustomRoleSource.is_deleted.is_(False),
    ).limit(1))
    if source is None:
        return {
            "templateProvenance": {
                "authority": "ROLE_PERMISSION",
                "provenanceStatus": "MISSING_CUSTOM_ROLE_SOURCE",
                "roleVersion": int(role.version or 0),
                "upgradePolicy": "DERIVED_PINNED",
            },
            "drift": {
                "detected": True,
                "provenanceMissing": True,
                "runtimeVsRecorded": {"addedInRuntime": sorted(runtime), "removedFromRuntime": []},
                "storedDrift": {},
            },
            "templateImpact": {
                "automaticUpgrade": False,
                "status": "UNAVAILABLE_PROVENANCE_MISSING",
                "wouldAdd": [],
                "wouldRemove": [],
            },
        }

    source_code = assert_school_role_template_code(source.source_template_code)
    source_version = int(source.source_template_version or 0)
    source_template = _template_version(db, source_code, source_version)
    latest_template = _latest_template(db, source_code)
    recorded = set(_json_items(source.permission_codes_json or {}))
    source_snapshot = set(_template_permissions(source_template))
    latest = set(_template_permissions(latest_template))

    runtime_added = sorted(runtime - recorded)
    runtime_removed = sorted(recorded - runtime)
    source_added = sorted(runtime - source_snapshot) if source_template is not None else []
    source_removed = sorted(source_snapshot - runtime) if source_template is not None else []
    latest_version = int(latest_template.template_version or 0) if latest_template is not None else None
    version_drift = latest_version is not None and latest_version != source_version
    detected = bool(runtime_added or runtime_removed or version_drift or source_template is None)

    return {
        "templateProvenance": {
            "authority": "ROLE_PERMISSION",
            "provenanceStatus": "PINNED" if source_template is not None else "SOURCE_VERSION_NOT_FOUND",
            "sourceId": str(source.id),
            "sourceTemplateCode": source_code,
            "sourceTemplateVersion": source_version,
            "sourceTemplatePresent": source_template is not None,
            "currentTemplateVersion": latest_version,
            "roleVersion": int(role.version or 0),
            "sourceVersion": int(source.version or 0),
            "sourceStatus": source.status,
            "upgradePolicy": "DERIVED_PINNED",
        },
        "drift": {
            "detected": detected,
            "templateVersionDrift": version_drift,
            "runtimeVsRecorded": {
                "addedInRuntime": runtime_added,
                "removedFromRuntime": runtime_removed,
            },
            "runtimeVsSourceTemplate": {
                "addedInRuntime": source_added,
                "removedFromRuntime": source_removed,
            },
            "storedDrift": dict(source.drift_json or {}),
        },
        "templateImpact": {
            "automaticUpgrade": False,
            "status": "READY" if latest_template is not None else "CURRENT_TEMPLATE_NOT_FOUND",
            "targetTemplateVersion": latest_version,
            "wouldAdd": sorted(latest - runtime),
            "wouldRemove": sorted(runtime - latest),
        },
    }


def _role_governance(db, tenant_id: int, role: Role, runtime_permissions: list[str]) -> dict:
    if str(role.role_type or "SYSTEM").upper() != "CUSTOM":
        return _system_role_governance(role, runtime_permissions)
    return _custom_role_governance(db, tenant_id, role, runtime_permissions)


def school_template_impact(template_id: int) -> dict:
    """Return impact for the current school only; never expose other tenants' pinned roles."""
    tid = _tenant_id()
    db = get_sessionmaker()()
    try:
        template = db.scalar(select(RoleTemplate).where(
            RoleTemplate.id == int(template_id),
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.is_deleted.is_(False),
        ).limit(1))
        if template is None:
            raise AppException("DATA_NOT_FOUND", "角色模板不存在", http_status=404)
        code = assert_school_role_template_code(template.template_code)
        target = set(_template_permissions(template))
        latest = _latest_template(db, code)

        sources = list(db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tid,
            CustomRoleSource.source_template_code == code,
            CustomRoleSource.is_deleted.is_(False),
        ).order_by(CustomRoleSource.role_code)).all())
        role_codes = [source.role_code for source in sources]
        roles = list(db.scalars(select(Role).where(
            Role.tenant_id == tid,
            Role.role_code.in_(role_codes) if role_codes else False,
            Role.is_deleted.is_(False),
        )).all()) if role_codes else []
        role_by_code = {role.role_code: role for role in roles}

        role_ids = [role.id for role in roles]
        runtime_by_role: dict[int, set[str]] = defaultdict(set)
        if role_ids:
            rows = db.execute(select(RolePermission.role_id, Permission.permission_code).join(
                Permission, Permission.id == RolePermission.permission_id
            ).where(
                RolePermission.tenant_id == tid,
                RolePermission.role_id.in_(role_ids),
                RolePermission.status == "ACTIVE",
                RolePermission.is_deleted.is_(False),
            )).all()
            for role_id, permission_code in rows:
                runtime_by_role[int(role_id)].add(str(permission_code))

        affected = []
        for source in sources:
            role = role_by_code.get(source.role_code)
            runtime = set(runtime_by_role.get(int(role.id), set())) if role is not None else set()
            recorded = set(_json_items(source.permission_codes_json or {}))
            affected.append({
                "roleCode": source.role_code,
                "runtimeRoleId": str(role.id) if role is not None else None,
                "runtimeRoleMissing": role is None,
                "roleVersion": int(role.version or 0) if role is not None else None,
                "sourceTemplateVersion": int(source.source_template_version or 0),
                "sourceVersion": int(source.version or 0),
                "storedDrift": dict(source.drift_json or {}),
                "runtimeVsRecorded": {
                    "addedInRuntime": sorted(runtime - recorded),
                    "removedFromRuntime": sorted(recorded - runtime),
                },
                "wouldAdd": sorted(target - runtime),
                "wouldRemove": sorted(runtime - target),
                "automaticUpgrade": False,
            })

        return {
            "tenantId": str(tid),
            "templateId": str(template.id),
            "templateCode": code,
            "templateVersion": int(template.template_version or 0),
            "currentPublishedTemplateVersion": int(latest.template_version or 0) if latest is not None else None,
            "isCurrentPublishedVersion": bool(latest is not None and int(latest.id) == int(template.id)),
            "permissionCount": len(target),
            "affectedPinnedCustomRoleCount": len(affected),
            "automaticUpgrade": False,
            "roles": affected,
        }
    finally:
        db.close()


def explain_subject_access(user_id: int, *, module_key: str, permission_code: str) -> dict:
    tid = _tenant_id()
    meta = permission_meta(permission_code)
    if meta and (
        meta.get("plane") != "TENANT"
        or not bool(meta.get("tenantAssignable"))
        or str(permission_code).startswith("enterprise.internship.")
    ):
        return {
            "allowed": False,
            "iamAllowed": False,
            "reasonCode": "PERMISSION_NOT_SCHOOL_ASSIGNABLE",
            "permissionCode": permission_code,
            "catalog": meta,
            "message": "学校管理员不能把企业成员权限授予学校用户；企业权限由 EnterpriseMember/Grant 管理。",
        }

    db = get_sessionmaker()()
    try:
        subject = db.scalar(select(User).where(
            User.id == int(user_id), User.tenant_id == tid, User.is_deleted.is_(False)
        ))
        if subject is None:
            raise AppException("DATA_NOT_FOUND", "学校成员不存在", http_status=404)
        if str(subject.status or "").upper() != "ACTIVE":
            return {
                "allowed": False,
                "iamAllowed": False,
                "reasonCode": "SUBJECT_INACTIVE",
                "subject": {"userId": str(subject.id), "loginName": subject.login_name, "realName": subject.real_name, "status": subject.status},
            }
        roles = list(db.scalars(select(Role).join(
            UserRole, UserRole.role_id == Role.id
        ).where(
            UserRole.tenant_id == tid,
            UserRole.user_id == subject.id,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.tenant_id == tid,
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        ).order_by(Role.role_code)).all())
        role_rows = []
        iam_candidate = None
        for role in roles:
            actor = {
                "userId": f"db-{subject.id}",
                "tenantId": str(tid),
                "userType": subject.user_type,
                "currentRoleCode": role.role_code,
                "activeContextId": f"role:{role.id}" if str(role.role_type or "").upper() == "CUSTOM" else "",
            }
            decision = explain_tenant_access(
                actor,
                module_key=module_key,
                permission_code=permission_code,
                data_scope_allowed=None,
                domain_guard=None,
            )
            if decision.get("iamAllowed"):
                iam_candidate = decision
            runtime_permissions = _role_permissions(db, tid, role)
            role_rows.append({
                "roleId": str(role.id),
                "roleCode": role.role_code,
                "roleName": role.role_name,
                "roleType": role.role_type,
                "roleVersion": int(role.version or 0),
                "permissionPatterns": runtime_permissions,
                **_role_governance(db, tid, role, runtime_permissions),
                "decision": {
                    "allowed": decision.get("allowed"),
                    "iamAllowed": decision.get("iamAllowed", False),
                    "reasonCode": decision.get("reasonCode"),
                    "dataScope": (decision.get("context") or {}).get("dataScopeSummary"),
                    "moduleAccessHealthy": (decision.get("context") or {}).get("moduleAccessHealthy"),
                },
            })
        if iam_candidate:
            return {
                "allowed": False,
                "iamAllowed": True,
                "finalDecision": "NOT_EVALUATED",
                "reasonCode": "DOMAIN_GUARD_NOT_EVALUATED",
                "message": "模块授权、学校角色权限已通过；最终是否能管理具体招聘季仍必须由 Internship Domain Guard 按学院/批次/业务关系裁决。",
                "subject": {"userId": str(subject.id), "loginName": subject.login_name, "realName": subject.real_name, "status": subject.status},
                "moduleKey": module_key,
                "permissionCode": permission_code,
                "roles": role_rows,
            }
        reason = "NO_ACTIVE_ROLE" if not roles else (role_rows[0]["decision"]["reasonCode"] if role_rows else "PERMISSION_DENIED")
        if any(item["decision"]["reasonCode"] == "MODULE_NOT_ENTITLED" for item in role_rows):
            reason = "MODULE_NOT_ENTITLED"
        elif any(item["decision"]["reasonCode"] == "MODULE_ACCESS_UNAVAILABLE" for item in role_rows):
            reason = "MODULE_ACCESS_UNAVAILABLE"
        else:
            reason = "PERMISSION_DENIED" if roles else reason
        return {
            "allowed": False,
            "iamAllowed": False,
            "reasonCode": reason,
            "subject": {"userId": str(subject.id), "loginName": subject.login_name, "realName": subject.real_name, "status": subject.status},
            "moduleKey": module_key,
            "permissionCode": permission_code,
            "roles": role_rows,
        }
    finally:
        db.close()


def workspace_summary() -> dict:
    tid = _tenant_id()
    db = get_sessionmaker()()
    try:
        role_count = int(db.scalar(select(func.count(Role.id)).where(
            Role.tenant_id == tid, Role.is_deleted.is_(False)
        )) or 0)
        member_count = int(db.scalar(select(func.count(User.id)).where(
            User.tenant_id == tid, User.is_deleted.is_(False)
        )) or 0)
        custom_source_count = int(db.scalar(select(func.count(CustomRoleSource.id)).where(
            CustomRoleSource.tenant_id == tid, CustomRoleSource.is_deleted.is_(False)
        )) or 0)
        missing_provenance_count = int(db.scalar(select(func.count(Role.id)).where(
            Role.tenant_id == tid,
            Role.role_type == "CUSTOM",
            Role.is_deleted.is_(False),
            ~Role.role_code.in_(select(CustomRoleSource.role_code).where(
                CustomRoleSource.tenant_id == tid,
                CustomRoleSource.is_deleted.is_(False),
            )),
        )) or 0)
        return {
            "tenantId": str(tid),
            "roleCount": role_count,
            "memberCount": member_count,
            "customRoleSourceCount": custom_source_count,
            "customRoleMissingProvenanceCount": missing_provenance_count,
            "surfaces": ["roles", "templates", "members", "permissions", "dataScopes", "delegations", "securityChanges", "accessExplain"],
            "enterpriseRoleAdministration": "DENIED_FROM_SCHOOL_IAM",
        }
    finally:
        db.close()
