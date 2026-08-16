"""Control Plane compatibility cutover for temporary school-role delegation.

Legacy delegation rows stored only ``roleCode`` and expanded that role at read time.
After SCHOOL_ADMIN wildcard retirement, that couples an existing temporary grant to
future role growth. New rows therefore pin the canonical concrete TENANT permission
snapshot at creation; runtime consumes that immutable snapshot. Historical rows keep
the old resolver only as a read-only migration fallback until they expire/revoke.
"""
from __future__ import annotations

from uuid import uuid4

from app.core.exceptions import AppException
from app.services import system_governance_service as _legacy
from app.services import system_role_shadow_service as shadow

AUTHORITY_SOURCE = "CANONICAL_TENANT_ROLE_SNAPSHOT"


def _delegated_permission_snapshot(role_code: str) -> tuple[str, ...]:
    from app.core.permissions import ROLE_PERMISSIONS

    code = str(role_code or "").strip().upper()
    patterns = set(ROLE_PERMISSIONS.get(code) or set())
    if not patterns:
        raise AppException("VALIDATION_ERROR", "临时角色不存在或没有可授予权限")
    if code.startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "学校临时授权禁止授予平台角色")
    # Preserve the existing hard boundary: SCHOOL_ADMIN / any full wildcard role
    # is never eligible for temporary delegation even though B8 can expand it.
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
    # This helper intentionally reads permanent/base authority only. Temporary
    # privileges therefore can never be re-delegated into a longer-lived chain.
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
    """Resolve only the pinned concrete snapshot for new delegation rows."""
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

        # N-1 rows have no pinned snapshot. They keep their historical resolver
        # only until expiry/revoke; no new writer is allowed to create such rows.
        role_code = str(item.get("roleCode") or "").strip().upper()
        permissions.update(ROLE_PERMISSIONS.get(role_code) or set())
    return permissions


def install_legacy_delegation_authority_adapter() -> None:
    """Install the Control Plane writer/reader on the frozen compatibility module."""
    _legacy.create_delegation = create_delegation
    _legacy.active_delegation_permission_patterns = active_delegation_permission_patterns
