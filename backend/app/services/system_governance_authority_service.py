"""Control Plane compatibility cutovers for frozen System governance services.

Temporary delegation is pinned to a concrete canonical permission snapshot so an
active grant cannot silently grow when a role changes.  The legacy role-template
bootstrap is retained for its bundle/wildcard migration evidence, but every call is
finished by B8 published-template convergence so its runtime result can never leave
pre-catalog permissions in the published SYSTEM-role Authority.
"""
from __future__ import annotations

import os
from uuid import uuid4

from app.core.exceptions import AppException
from app.services import permission_bundle_service as _bundles
from app.services import system_governance_service as _legacy
from app.services import system_role_shadow_service as shadow

AUTHORITY_SOURCE = "CANONICAL_TENANT_ROLE_SNAPSHOT"
_ORIGINAL_BOOTSTRAP_FROM_CODE = _bundles.bootstrap_from_code


def _delegated_permission_snapshot(role_code: str) -> tuple[str, ...]:
    from app.core.permissions import ROLE_PERMISSIONS

    code = str(role_code or "").strip().upper()
    patterns = set(ROLE_PERMISSIONS.get(code) or set())
    if not patterns:
        raise AppException("VALIDATION_ERROR", "临时角色不存在或没有可授予权限")
    if code.startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "学校临时授权禁止授予平台角色")
    if "*" in patterns:
        raise AppException("NO_PERMISSION", "临时授权禁止授予全量通配权限")
    concrete = tuple(shadow.expected_system_role_permissions(code))
    if not concrete:
        raise AppException("VALIDATION_ERROR", "临时角色在当前权限目录中没有可授予权限")
    return concrete


def create_delegation(user: dict, body: dict) -> dict:
    from app.core.permissions import assert_delegable_permission_codes
    from app.services import audit_log

    grantee = str(body.get("granteeUserNo") or "").strip()
    role_code = str(body.get("roleCode") or "").strip().upper()
    expires_at = str(body.get("expiresAt") or "").strip()
    reason = str(body.get("reason") or "").strip()
    expected = body.get("expectedVersion")
    if not grantee or not role_code or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "受权人工号、角色与原因（≥5字）必填")
    if not expires_at or expires_at <= _legacy._now():
        raise AppException("VALIDATION_ERROR", "到期时间必须晚于当前时间")

    permission_codes = _delegated_permission_snapshot(role_code)
    assert_delegable_permission_codes(user, permission_codes)

    grantee_user_id, grantee_login = _legacy._resolve_grantee(grantee)
    items = _legacy.list_delegations()
    _, current_version = _legacy._load_with_version(_legacy.DOC_DELEGATIONS)
    if expected is not None and int(expected) != current_version:
        raise AppException("DATA_CONFLICT", "临时授权已被他人更新，请刷新后重试")

    row = {
        "id": str(uuid4()),
        "granteeUserId": str(grantee_user_id),
        "granteeUserNo": grantee_login,
        "roleCode": role_code,
        "permissionCodes": list(permission_codes),
        "authoritySource": AUTHORITY_SOURCE,
        "expiresAt": expires_at,
        "reason": reason,
        "status": "ACTIVE",
        "statusLabel": "生效中",
        "createdAt": _legacy._now(),
        "createdBy": (user or {}).get("realName") or "系统",
        "effective": True,
        "version": 1,
        "docVersion": current_version + 1,
        "note": "临时授权固定为创建时的显式权限快照；过期或回收后立即失效",
    }
    items.insert(0, row)
    _legacy._save(
        _legacy.DOC_DELEGATIONS,
        items,
        user,
        expected_version=current_version,
    )
    audit_log.record(
        "DELEGATION_CREATE",
        f"delegation:{row['id']}",
        detail={
            "grantee": grantee,
            "roleCode": role_code,
            "expiresAt": expires_at,
            "reason": reason,
            "permissionCount": len(permission_codes),
            "authoritySource": AUTHORITY_SOURCE,
            "moduleCode": "systemAdmin",
        },
    )
    return row


def active_delegation_permission_patterns(user: dict) -> set[str]:
    """Resolve pinned concrete snapshots; N-1 rows keep read-only expiry fallback."""
    from app.core.permissions import ROLE_PERMISSIONS

    login = str((user or {}).get("loginName") or (user or {}).get("userNo") or "").strip()
    user_id = str((user or {}).get("userId") or "").removeprefix("db-").strip()
    if not login and not user_id:
        return set()

    permissions: set[str] = set()
    now = _legacy._now()
    for item in _legacy.list_delegations():
        if item.get("status") != "ACTIVE" or not item.get("effective", True):
            continue
        stable_target = str(item.get("granteeUserId") or "").strip()
        if stable_target:
            if not user_id or stable_target != user_id:
                continue
        elif str(item.get("granteeUserNo") or "").strip() != login:
            continue
        if item.get("expiresAt") and item["expiresAt"] < now:
            continue

        snapshot = {
            str(code).strip()
            for code in (item.get("permissionCodes") or [])
            if str(code).strip()
        }
        if snapshot:
            permissions.update(snapshot)
            continue

        role_code = str(item.get("roleCode") or "").strip().upper()
        permissions.update(ROLE_PERMISSIONS.get(role_code) or set())
    return permissions


def bootstrap_permission_governance_from_code(*, tenant_id: int | None = None) -> dict:
    """Keep legacy discovery evidence, then converge runtime templates to B8 truth."""
    result = _ORIGINAL_BOOTSTRAP_FROM_CODE(tenant_id=tenant_id)
    from app.core.context import get_current_user_ctx

    actor = get_current_user_ctx() or {}
    raw_actor = actor.get("userId") or actor.get("id") or 0
    try:
        actor_id = int(str(raw_actor).removeprefix("db-") or 0)
    except (TypeError, ValueError):
        actor_id = 0
    source = str(
        os.getenv("RELEASE_SHA")
        or os.getenv("GIT_SHA")
        or os.getenv("GITHUB_SHA")
        or "control-plane-runtime-bootstrap"
    ).strip()
    convergence = shadow.converge_published_system_templates(
        actor_user_id=actor_id,
        source_commit_sha=source,
    )
    return {
        **result,
        "authority": "CONTROL_PLANE_B8_PUBLISHED_TEMPLATE",
        "canonicalConvergence": convergence,
    }


def install_legacy_delegation_authority_adapter() -> None:
    """Install named cutovers on the frozen compatibility modules once per process."""
    _legacy.create_delegation = create_delegation
    _legacy.active_delegation_permission_patterns = active_delegation_permission_patterns
    _bundles.bootstrap_from_code = bootstrap_permission_governance_from_code
