"""School IAM Access Explain orchestration.

This service does not invent a second data-scope or domain rule engine. It composes
three existing authorities in their production order:

1. ``effective_access.explain_tenant_access`` for tenant/module/permission IAM;
2. ``data_scope_service.simulate_access`` for live business relationships;
3. ``scope_policy_service.decide`` for DENY/sensitive/relation/ALLOW precedence.

A resource-less explain request is deliberately fail-closed with
``RESOURCE_CONTEXT_REQUIRED`` instead of returning an indeterminate decision.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.effective_access import explain_tenant_access
from app.core.exceptions import AppException
from app.core.permission_catalog import permission_meta
from app.db.session import get_sessionmaker
from app.models import Role, User, UserRole
from app.modules.system_admin.services.school_iam_authority_projection_service import (
    _role_governance,
    _role_permissions,
    _tenant_id,
)
from app.services import data_scope_service, scope_policy_service
from app.services.auth_service_db import ROLE_DEFAULT_SCOPE

_RESOURCE_CONTEXT_REQUIRED = "RESOURCE_CONTEXT_REQUIRED"
_DOMAIN_GUARD_INVALID_CONTEXT = "DOMAIN_GUARD_INVALID_CONTEXT"


def _scope_code_for_role(role: Role) -> str:
    """Resolve the same structured/fallback scope policy used by real login contexts."""
    configured = data_scope_service.resolve_role_scope_code(role)
    if configured:
        return data_scope_service.normalize_scope(configured)
    fallback = ROLE_DEFAULT_SCOPE.get(str(role.role_code or ""), ("ASSIGNED", ""))[0]
    return data_scope_service.normalize_scope(fallback)


def _resource_payload(
    *,
    scope_target_type: str | None,
    scope_target_id: str | None,
    resource_type: str | None,
    resource_id: str | None,
) -> tuple[str, dict]:
    """Build the narrow resource facts expected by existing scope providers.

    No ownership fact is accepted from the caller.  The caller supplies only object
    identifiers; providers resolve ownership/relationships from their authority tables.
    """
    target_type = str(scope_target_type or "").upper()
    rtype = str(resource_type or target_type or "RESOURCE").upper()
    payload: dict[str, str] = {}

    if target_type == "CLASS" and scope_target_id:
        payload["classId"] = str(scope_target_id)
    elif target_type == "MAJOR" and scope_target_id:
        payload["majorId"] = str(scope_target_id)
    elif target_type == "COLLEGE" and scope_target_id:
        payload["collegeId"] = str(scope_target_id)

    if resource_id:
        rid = str(resource_id)
        if rtype in {"STUDENT", "INTERN_STUDENT", "GRADUATION_STUDENT"}:
            payload["studentId"] = rid
        elif rtype in {"DORM_BUILDING", "BUILDING"}:
            payload["buildingId"] = rid
        elif rtype in {"USER", "SELF", "OWNER"}:
            payload["ownerUserId"] = rid
        elif rtype == "CLASS":
            payload["classId"] = rid
        elif rtype == "MAJOR":
            payload["majorId"] = rid
        elif rtype == "COLLEGE":
            payload["collegeId"] = rid
        else:
            # Generic object IDs are never interpreted as ownership; they are retained
            # only so CUSTOM/object-based providers can fail closed or match configured IDs.
            payload["objectId"] = rid
    return rtype, payload


def _domain_guard_for_role(
    *,
    tenant_id: int,
    subject: User,
    role: Role,
    actor: dict,
    scope_target_type: str | None,
    scope_target_id: str | None,
    resource_type: str | None,
    resource_id: str | None,
) -> dict:
    if not scope_target_type or not scope_target_id:
        return {
            "allowed": False,
            "reasonCode": _RESOURCE_CONTEXT_REQUIRED,
            "details": {
                "authority": "SCOPE_POLICY_SERVICE",
                "message": "必须提供 scopeTargetType/scopeTargetId 才能形成业务最终访问结论",
            },
        }

    rtype, resource = _resource_payload(
        scope_target_type=scope_target_type,
        scope_target_id=scope_target_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    relation = data_scope_service.simulate_access(
        actor,
        resource_type=rtype,
        resource=resource,
    )
    try:
        policy = scope_policy_service.decide(
            str(role.role_code or ""),
            target_type=str(scope_target_type).upper(),
            target_id=str(scope_target_id),
            business_relation_allows=bool(relation.get("allowed")),
            tenant_id=int(tenant_id),
        )
    except AppException as exc:
        return {
            "allowed": False,
            "reasonCode": _DOMAIN_GUARD_INVALID_CONTEXT,
            "details": {
                "authority": "SCOPE_POLICY_SERVICE",
                "scopeTargetType": str(scope_target_type).upper(),
                "scopeTargetId": str(scope_target_id),
                "errorCode": getattr(exc, "code", None),
                "message": getattr(exc, "message", None) or str(exc),
            },
        }

    allowed = str(policy.get("decision") or "").upper() == "ALLOW"
    return {
        "allowed": allowed,
        "reasonCode": "ALLOW" if allowed else str(policy.get("reasonCode") or "DOMAIN_GUARD_DENIED"),
        "details": {
            "authority": "SCOPE_POLICY_SERVICE",
            "businessRelationAuthority": "DATA_SCOPE_SERVICE",
            "subjectUserId": str(subject.id),
            "roleCode": role.role_code,
            "scopeCode": actor.get("dataScope"),
            "resourceType": rtype,
            "businessRelation": relation,
            "scopePolicy": policy,
        },
    }


def explain_subject_access(
    user_id: int,
    *,
    module_key: str,
    permission_code: str,
    scope_target_type: str | None = None,
    scope_target_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> dict:
    """Return a deterministic school-side IAM + data-scope + domain final decision."""
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
            "finalDecision": "DENY",
            "reasonCode": "PERMISSION_NOT_SCHOOL_ASSIGNABLE",
            "permissionCode": permission_code,
            "catalog": meta,
            "message": "学校管理员不能把企业成员权限授予学校用户；企业权限由 EnterpriseMember/Grant 管理。",
        }

    db = get_sessionmaker()()
    try:
        subject = db.scalar(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tid,
            User.is_deleted.is_(False),
        ))
        if subject is None:
            raise AppException("DATA_NOT_FOUND", "学校成员不存在", http_status=404)
        subject_payload = {
            "userId": str(subject.id),
            "loginName": subject.login_name,
            "realName": subject.real_name,
            "status": subject.status,
        }
        if str(subject.status or "").upper() != "ACTIVE":
            return {
                "allowed": False,
                "iamAllowed": False,
                "finalDecision": "DENY",
                "reasonCode": "SUBJECT_INACTIVE",
                "subject": subject_payload,
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

        role_rows: list[dict] = []
        allowed_role = None
        iam_allowed_rows: list[dict] = []
        for role in roles:
            scope_code = _scope_code_for_role(role)
            actor = {
                "userId": f"db-{subject.id}",
                "loginName": subject.login_name,
                "tenantId": str(tid),
                "userType": subject.user_type,
                "currentRoleCode": role.role_code,
                "activeContextId": f"role:{role.id}" if str(role.role_type or "").upper() == "CUSTOM" else "",
                "dataScope": scope_code,
            }
            guard = _domain_guard_for_role(
                tenant_id=tid,
                subject=subject,
                role=role,
                actor=actor,
                scope_target_type=scope_target_type,
                scope_target_id=scope_target_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            # dataScope=True means the scope context itself was resolved.  The actual
            # target/rule/relation decision is delegated to the canonical Domain Guard
            # composed above, so explicit ALLOW/DENY precedence is not short-circuited.
            decision = explain_tenant_access(
                actor,
                module_key=module_key,
                permission_code=permission_code,
                data_scope_allowed=True,
                domain_guard=guard,
            )
            iam_allowed = bool(decision.get("allowed") or decision.get("iamAllowed"))
            runtime_permissions = _role_permissions(db, tid, role)
            row = {
                "roleId": str(role.id),
                "roleCode": role.role_code,
                "roleName": role.role_name,
                "roleType": role.role_type,
                "roleVersion": int(role.version or 0),
                "permissionCodes": runtime_permissions,
                "permissionPatterns": runtime_permissions,
                **_role_governance(db, tid, role, runtime_permissions),
                "decision": {
                    "allowed": bool(decision.get("allowed")),
                    "iamAllowed": iam_allowed,
                    "reasonCode": decision.get("reasonCode"),
                    "dataScope": scope_code,
                    "moduleAccessHealthy": (decision.get("context") or {}).get("moduleAccessHealthy"),
                    "domainGuard": guard,
                    "checks": decision.get("checks") or [],
                },
            }
            role_rows.append(row)
            if bool(decision.get("allowed")) and allowed_role is None:
                allowed_role = row
            if iam_allowed:
                iam_allowed_rows.append(row)

        common = {
            "subject": subject_payload,
            "moduleKey": module_key,
            "permissionCode": permission_code,
            "scopeTargetType": str(scope_target_type).upper() if scope_target_type else None,
            "scopeTargetId": str(scope_target_id) if scope_target_id else None,
            "resourceType": str(resource_type).upper() if resource_type else None,
            "resourceIdSupplied": bool(resource_id),
            "roles": role_rows,
        }
        if allowed_role is not None:
            return {
                "allowed": True,
                "iamAllowed": True,
                "finalDecision": "ALLOW",
                "reasonCode": "ALLOW",
                "message": "模块、权限、数据范围与 Domain Guard 均通过。",
                "winningRoleCode": allowed_role["roleCode"],
                **common,
            }
        if iam_allowed_rows:
            denied = iam_allowed_rows[0]
            reason = denied["decision"].get("reasonCode") or "DOMAIN_GUARD_DENIED"
            return {
                "allowed": False,
                "iamAllowed": True,
                "finalDecision": "DENY",
                "reasonCode": reason,
                "message": "IAM 已通过，但数据范围/业务关系/显式范围策略未形成最终允许。",
                **common,
            }

        reason = "NO_ACTIVE_ROLE" if not roles else "PERMISSION_DENIED"
        if any(item["decision"]["reasonCode"] == "MODULE_NOT_ENTITLED" for item in role_rows):
            reason = "MODULE_NOT_ENTITLED"
        elif any(item["decision"]["reasonCode"] == "MODULE_ACCESS_UNAVAILABLE" for item in role_rows):
            reason = "MODULE_ACCESS_UNAVAILABLE"
        return {
            "allowed": False,
            "iamAllowed": False,
            "finalDecision": "DENY",
            "reasonCode": reason,
            **common,
        }
    finally:
        db.close()
