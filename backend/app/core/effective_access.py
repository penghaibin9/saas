"""Canonical EffectiveAccess projection and explain contracts.

This module owns the outer IAM decision language only. Internship/enterprise
business authority stays in its domain: callers pass domain-guard facts into
these explain functions; this module never imports E-series models/services.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.permissions import get_effective_access_context, has_permission
from app.core.platform_principal import PermissionPlane, principal_plane

MODULE_ACCESS_UNAVAILABLE = "MODULE_ACCESS_UNAVAILABLE"
MODULE_NOT_ENTITLED = "MODULE_NOT_ENTITLED"
PERMISSION_DENIED = "PERMISSION_DENIED"
DATA_SCOPE_DENIED = "DATA_SCOPE_DENIED"
DOMAIN_GUARD_NOT_EVALUATED = "DOMAIN_GUARD_NOT_EVALUATED"
DOMAIN_GUARD_DENIED = "DOMAIN_GUARD_DENIED"
ENTERPRISE_PRINCIPAL_REQUIRED = "ENTERPRISE_PRINCIPAL_REQUIRED"
ENTERPRISE_MEMBER_INACTIVE = "ENTERPRISE_MEMBER_INACTIVE"
GRANT_EXPIRED = "GRANT_EXPIRED"
CAMPAIGN_NOT_ACCEPTED = "CAMPAIGN_NOT_ACCEPTED"
WRONG_COMPANY = "WRONG_COMPANY"
RESOURCE_SCOPE_DENIED = "RESOURCE_SCOPE_DENIED"
STATE_NOT_ALLOWED = "STATE_NOT_ALLOWED"


def _tenant_id(user: dict | None) -> int | None:
    try:
        request_tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        request_tid = 0
    if request_tid:
        return request_tid
    try:
        value = int((user or {}).get("tenantId") or 0)
    except (TypeError, ValueError):
        value = 0
    return value or None


def _security_revision(tenant_id: int | None) -> tuple[int | None, bool, str]:
    if not tenant_id:
        return 0, True, ""
    try:
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            return 0, True, ""
        from app.models.security_change import SecurityActivation
        db = get_sessionmaker()()
        try:
            revision = db.scalar(select(func.max(SecurityActivation.revision)).where(
                SecurityActivation.tenant_id == int(tenant_id),
                SecurityActivation.is_deleted.is_(False),
            ))
            return int(revision or 0), True, ""
        finally:
            db.close()
    except Exception:
        return None, False, "安全版本读取失败；上下文禁止作为可缓存授权真值"


def _permission_digest(patterns: list[str]) -> str:
    payload = json.dumps(sorted(set(patterns)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_effective_access_context(user: dict | None) -> dict:
    actor = dict(user or {})
    base = get_effective_access_context(actor)
    tenant_id = _tenant_id(actor)
    patterns = list(base.get("permissionPatterns") or [])
    digest = _permission_digest(patterns)
    revision, revision_healthy, revision_error = _security_revision(tenant_id)
    active_context_id = str(actor.get("activeContextId") or "")
    role_code = str(base.get("roleCode") or actor.get("currentRoleCode") or actor.get("userType") or "")
    if active_context_id.startswith("enterprise-member:") or role_code == "ENTERPRISE_MEMBER":
        principal_type = "ENTERPRISE"
    elif principal_plane(actor) is PermissionPlane.PLATFORM:
        principal_type = "PLATFORM_WORKFORCE"
    else:
        principal_type = "TENANT_USER"
    plane = principal_plane(actor).value
    subject_id = str(actor.get("userId") or "")
    ctx_key = None
    if revision_healthy:
        key_payload = "|".join([
            plane,
            principal_type,
            str(tenant_id or 0),
            subject_id,
            active_context_id,
            digest,
            str(revision or 0),
            str(base.get("permissionVersion") or ""),
        ])
        ctx_key = hashlib.sha256(key_payload.encode("utf-8")).hexdigest()[:32]
    return {
        **base,
        "principalPlane": plane,
        "principalType": principal_type,
        "subjectId": subject_id,
        "tenantId": str(tenant_id or ""),
        "activeContextId": active_context_id,
        "permissionDigest": digest,
        "securityRevision": revision,
        "securityRevisionHealthy": revision_healthy,
        "securityRevisionError": revision_error,
        "ctxKey": ctx_key,
        "dataScopeSummary": base.get("dataScope"),
    }


def explain_tenant_access(
    user: dict | None,
    *,
    module_key: str,
    permission_code: str,
    data_scope_allowed: bool | None = None,
    domain_guard: dict[str, Any] | None = None,
) -> dict:
    """Explain school-side IAM without pretending to replace domain guards."""
    actor = dict(user or {})
    context = build_effective_access_context(actor)
    checks: list[dict] = []

    if context.get("principalPlane") != "TENANT" or context.get("principalType") == "ENTERPRISE":
        return {
            "allowed": False,
            "reasonCode": "TENANT_PRINCIPAL_REQUIRED",
            "checks": [{"check": "principal", "passed": False}],
            "context": context,
        }

    if not context.get("moduleAccessHealthy"):
        return {
            "allowed": False,
            "reasonCode": MODULE_ACCESS_UNAVAILABLE,
            "checks": [{"check": "moduleEntitlement", "passed": False, "healthy": False}],
            "context": context,
        }
    entitled = module_key in set(context.get("moduleEntitlements") or [])
    checks.append({"check": "moduleEntitlement", "passed": entitled, "moduleKey": module_key})
    if not entitled:
        return {"allowed": False, "reasonCode": MODULE_NOT_ENTITLED, "checks": checks, "context": context}

    permission_allowed = has_permission(actor, permission_code)
    checks.append({"check": "permission", "passed": permission_allowed, "permissionCode": permission_code})
    if not permission_allowed:
        return {"allowed": False, "reasonCode": PERMISSION_DENIED, "checks": checks, "context": context}

    if data_scope_allowed is False:
        checks.append({"check": "dataScope", "passed": False})
        return {"allowed": False, "reasonCode": DATA_SCOPE_DENIED, "checks": checks, "context": context}
    checks.append({"check": "dataScope", "passed": data_scope_allowed, "evaluated": data_scope_allowed is not None})

    if domain_guard is None:
        checks.append({"check": "domainGuard", "passed": None, "evaluated": False})
        return {
            "allowed": False,
            "iamAllowed": True,
            "finalDecision": "NOT_EVALUATED",
            "reasonCode": DOMAIN_GUARD_NOT_EVALUATED,
            "checks": checks,
            "context": context,
        }

    domain_allowed = bool(domain_guard.get("allowed"))
    checks.append({"check": "domainGuard", "passed": domain_allowed, "details": domain_guard.get("details") or {}})
    if not domain_allowed:
        return {
            "allowed": False,
            "iamAllowed": True,
            "reasonCode": str(domain_guard.get("reasonCode") or DOMAIN_GUARD_DENIED),
            "checks": checks,
            "context": context,
        }
    return {"allowed": True, "reasonCode": "ALLOW", "checks": checks, "context": context}


def explain_enterprise_access(*, facts: dict[str, Any]) -> dict:
    """Explain E enterprise access from server-derived domain facts.

    The E Authority owns how these facts are obtained.  Control Plane only owns
    the shared reason-code language and never turns a permission match into an
    enterprise grant by itself.
    """
    ordered = [
        ("enterprisePrincipal", bool(facts.get("enterprisePrincipal")), ENTERPRISE_PRINCIPAL_REQUIRED),
        ("moduleEntitlement", bool(facts.get("moduleEntitled")), MODULE_NOT_ENTITLED),
        ("permission", bool(facts.get("permissionAllowed")), PERMISSION_DENIED),
        ("enterpriseMember", str(facts.get("memberStatus") or "").upper() == "ACTIVE", ENTERPRISE_MEMBER_INACTIVE),
        ("accessGrant", str(facts.get("grantStatus") or "").upper() == "ACTIVE", GRANT_EXPIRED),
        ("campaignEnterprise", str(facts.get("campaignStatus") or "").upper() == "ACCEPTED", CAMPAIGN_NOT_ACCEPTED),
        ("companyOwnership", bool(facts.get("companyMatches")), WRONG_COMPANY),
        ("resourceScope", bool(facts.get("resourceScopeAllowed")), RESOURCE_SCOPE_DENIED),
        ("stateMachine", bool(facts.get("stateAllowed")), STATE_NOT_ALLOWED),
    ]
    checks = []
    for name, passed, reason in ordered:
        checks.append({"check": name, "passed": passed})
        if not passed:
            return {"allowed": False, "reasonCode": reason, "checks": checks}
    return {"allowed": True, "reasonCode": "ALLOW", "checks": checks}
