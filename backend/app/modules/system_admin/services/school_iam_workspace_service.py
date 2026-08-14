"""B7 School IAM Workspace projection and Access Explain."""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.effective_access import explain_tenant_access
from app.core.exceptions import AppException
from app.core.permission_catalog import load_permission_catalog, permission_meta
from app.db.session import get_sessionmaker
from app.models import Permission, Role, RolePermission, User, UserRole
from app.models.permission_governance import CustomRoleSource, RoleTemplate


def _tenant_id() -> int:
    tid = int(current_tenant_id() or 0)
    if tid <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "学校 IAM 工作区缺少租户上下文", http_status=403)
    return tid


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
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.status.in_(("ACTIVE", "PUBLISHED")),
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_code, RoleTemplate.template_version.desc())).all())
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
                "permissions": sorted(set(ceiling.get("items") or [])),
                "immutable": True,
                "customRoleUpgradePolicy": "DERIVED_PINNED",
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
            role_rows.append({
                "roleId": str(role.id),
                "roleCode": role.role_code,
                "roleName": role.role_name,
                "roleType": role.role_type,
                "permissionPatterns": _role_permissions(db, tid, role),
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
        # Prefer a more specific common module denial over arbitrary first-role permission denial.
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
        role_count = int(db.scalar(select(__import__("sqlalchemy").func.count(Role.id)).where(
            Role.tenant_id == tid, Role.is_deleted.is_(False)
        )) or 0)
        member_count = int(db.scalar(select(__import__("sqlalchemy").func.count(User.id)).where(
            User.tenant_id == tid, User.is_deleted.is_(False)
        )) or 0)
        custom_source_count = int(db.scalar(select(__import__("sqlalchemy").func.count(CustomRoleSource.id)).where(
            CustomRoleSource.tenant_id == tid, CustomRoleSource.is_deleted.is_(False)
        )) or 0)
        return {
            "tenantId": str(tid),
            "roleCount": role_count,
            "memberCount": member_count,
            "customRoleSourceCount": custom_source_count,
            "surfaces": ["roles", "templates", "members", "permissions", "dataScopes", "delegations", "securityChanges", "accessExplain"],
            "enterpriseRoleAdministration": "DENIED_FROM_SCHOOL_IAM",
        }
    finally:
        db.close()
