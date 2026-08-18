"""Final hardening layer for Platform Workforce / PAM.

Keep the canonical runtime service intact and override only contracts that must
fail closed at the control-plane boundary:

* access-review creation accepts only a server-controlled scope and enforces a
  hard snapshot size bound before any campaign write;
* access-review closure requires an exact, duplicate-free decision set for the
  frozen snapshot; omitted items must never silently become KEEP;
* terminating another operator's support session is an administrative action
  and therefore additionally requires ``access.manage``.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.platform.services import platform_access_governance_runtime as _runtime

_REVIEW_TYPES = frozenset({_runtime.ASSIGNMENT, _runtime.ELEVATION, _runtime.SUPPORT})
_REVIEW_SCOPE_KEYS = frozenset({"configTypes", "tenantIds"})
_REVIEW_FORBIDDEN_PAYLOAD_KEYS = frozenset({"items", "recordIds", "snapshot", "snapshots"})


def _review_max_items() -> int:
    raw = str(os.getenv("PLATFORM_ACCESS_REVIEW_MAX_ITEMS", "500") or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException(
            "ACCESS_REVIEW_LIMIT_INVALID",
            "PLATFORM_ACCESS_REVIEW_MAX_ITEMS 必须是正整数",
            http_status=503,
        ) from None
    if value <= 0:
        raise AppException(
            "ACCESS_REVIEW_LIMIT_INVALID",
            "PLATFORM_ACCESS_REVIEW_MAX_ITEMS 必须是正整数",
            http_status=503,
        )
    return value


def _review_scope(payload: dict) -> dict:
    injected = sorted(key for key in _REVIEW_FORBIDDEN_PAYLOAD_KEYS if key in payload)
    if injected:
        raise AppException(
            "ACCESS_REVIEW_SCOPE_INVALID",
            "访问复核快照只能由服务器生成，禁止客户端提交 items/recordIds/snapshot",
            http_status=422,
            details={"forbiddenFields": injected},
        )

    raw = payload.get("scope")
    if raw in (None, ""):
        raw = {}
    if not isinstance(raw, dict):
        raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "访问复核 scope 必须是对象", http_status=422)
    unknown_keys = sorted(set(raw) - _REVIEW_SCOPE_KEYS)
    if unknown_keys:
        raise AppException(
            "ACCESS_REVIEW_SCOPE_INVALID",
            "访问复核 scope 包含未登记字段",
            http_status=422,
            details={"unknownScopeFields": unknown_keys},
        )

    raw_types = raw.get("configTypes")
    if raw_types is None:
        config_types = sorted(_REVIEW_TYPES)
    else:
        if not isinstance(raw_types, list) or not raw_types:
            raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "scope.configTypes 必须是非空列表", http_status=422)
        normalized_types = [str(value or "").strip() for value in raw_types]
        if any(not value for value in normalized_types) or len(set(normalized_types)) != len(normalized_types):
            raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "scope.configTypes 不能为空或重复", http_status=422)
        unknown_types = sorted(set(normalized_types) - _REVIEW_TYPES)
        if unknown_types:
            raise AppException(
                "ACCESS_REVIEW_SCOPE_INVALID",
                "scope.configTypes 包含未登记访问记录类型",
                http_status=422,
                details={"unknownConfigTypes": unknown_types},
            )
        config_types = sorted(normalized_types)

    raw_tenants = raw.get("tenantIds")
    tenant_ids: list[int] = []
    if raw_tenants is not None:
        if not isinstance(raw_tenants, list) or not raw_tenants:
            raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "scope.tenantIds 必须是非空正整数列表", http_status=422)
        try:
            tenant_ids = [int(value) for value in raw_tenants]
        except (TypeError, ValueError):
            raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "scope.tenantIds 必须是正整数", http_status=422) from None
        if any(value <= 0 for value in tenant_ids) or len(set(tenant_ids)) != len(tenant_ids):
            raise AppException("ACCESS_REVIEW_SCOPE_INVALID", "scope.tenantIds 只能包含不重复的正整数", http_status=422)
        tenant_ids.sort()

    return {"configTypes": config_types, "tenantIds": tenant_ids}


def _bounded_review_records(config_type: str, *, tenant_ids: list[int], limit: int) -> list[dict]:
    """Read only the active rows needed to prove the review fits its hard bound.

    The legacy list API intentionally serves operator screens and is unbounded.
    Access-review creation is different: it must never hydrate an arbitrarily
    large PlatformConfig set merely to discover that the campaign is too large.
    """
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        query = select(PlatformConfig).where(
            PlatformConfig.config_type == config_type,
            PlatformConfig.is_deleted.is_(False),
            PlatformConfig.enabled.is_(True),
        )
        if tenant_ids:
            query = query.where(PlatformConfig.tenant_id.in_(tuple(int(value) for value in tenant_ids)))
        rows = db.scalars(
            query.order_by(PlatformConfig.id.desc()).limit(int(limit))
        ).all()
        return [_runtime._base._row_to_dict(row) for row in rows]
    finally:
        db.close()


def create_access_review(payload: dict, *, actor: dict) -> dict:
    """Create one bounded, server-derived review snapshot.

    ``tenantIds`` is an exact tenant filter. Platform-global records have
    tenantId=0 and are intentionally excluded when a tenant filter is supplied;
    callers that also need global assignments/elevations must create a separate
    review scope rather than silently widening the campaign.
    """
    _runtime.assert_recent_platform_auth(actor, require_mfa=False)
    scope = _review_scope(payload)
    max_items = _review_max_items()
    key = _runtime._base._idempotent_key("review", payload.get("requestId"))
    expected = {
        "requestId": payload.get("requestId"),
        "name": str(payload.get("name") or "Platform Access Review").strip(),
        "dueAt": payload.get("dueAt"),
        "scope": scope,
    }
    replay = _runtime._same_or_conflict(
        _runtime._existing(_runtime.REVIEW, 0, key),
        expected,
        fields=("requestId", "name", "dueAt", "scope"),
    )
    if replay:
        return replay

    tenant_filter = set(scope["tenantIds"])
    snapshots: list[dict] = []
    for config_type in scope["configTypes"]:
        remaining = max_items - len(snapshots)
        rows = _bounded_review_records(
            config_type,
            tenant_ids=scope["tenantIds"],
            limit=remaining + 1,
        )
        for item in rows:
            if str(item.get("status") or "ACTIVE").upper() != "ACTIVE":
                continue
            tenant_id = int(item.get("tenantId") or 0)
            if tenant_filter and tenant_id not in tenant_filter:
                continue
            snapshots.append({
                "itemKey": f"{config_type}:{tenant_id}:{item.get('id')}",
                "configType": config_type,
                "tenantId": tenant_id,
                "recordId": str(item.get("id")),
                "version": _runtime._base._version(item.get("version")),
                "snapshot": {k: v for k, v in item.items() if k not in {"requestDigest"}},
                "decision": "PENDING",
            })
            if len(snapshots) > max_items:
                raise AppException(
                    "ACCESS_REVIEW_SCOPE_TOO_LARGE",
                    "访问复核范围超过单事务安全上限，请缩小 scope 后创建多个独立复核批次",
                    http_status=409,
                    details={"maxItems": max_items, "itemCountAtLeast": len(snapshots), "scope": scope},
                )

    data = {
        "requestId": payload.get("requestId"),
        "name": expected["name"],
        "dueAt": payload.get("dueAt"),
        "scope": scope,
        "maxItemsAtCreate": max_items,
        "status": "OPEN",
        "createdBy": actor.get("userId"),
        "items": snapshots,
    }
    return _runtime._base._save_atomic(
        _runtime.REVIEW,
        data,
        tenant_id=0,
        audit_action="PLATFORM_ACCESS_REVIEW_CHANGE",
        audit_detail={"action": "CREATE", "itemCount": len(snapshots), "scope": scope},
        key=key,
        create_idempotent=True,
    )


def _review_decisions(payload: dict) -> list[dict]:
    raw = payload.get("decisions") or []
    if not isinstance(raw, list):
        raise AppException("VALIDATION_ERROR", "复核决定必须是逐项列表", http_status=422)
    keys = [str(item.get("itemKey") or "").strip() for item in raw if isinstance(item, dict)]
    if len(keys) != len(raw) or any(not key for key in keys):
        raise AppException("VALIDATION_ERROR", "每条复核决定都必须包含 itemKey", http_status=422)
    if len(set(keys)) != len(keys):
        raise AppException("VALIDATION_ERROR", "复核决定存在重复 itemKey", http_status=422)
    invalid = [
        item for item in raw
        if str(item.get("decision") or "").upper() not in {"KEEP", "REVOKE"}
    ]
    if invalid:
        raise AppException("VALIDATION_ERROR", "复核决定只能是 KEEP / REVOKE", http_status=422)
    return raw


def close_access_review(review_id: str, payload: dict, *, actor: dict) -> dict:
    decisions = _review_decisions(payload)
    rows = [item for item in _runtime.list_records(_runtime.REVIEW) if str(item.get("id")) == str(review_id)]
    if not rows:
        raise AppException("DATA_NOT_FOUND", "访问复核不存在", http_status=404)
    review = rows[0]
    if str(review.get("status") or "").upper() != "OPEN":
        raise AppException("DATA_CONFLICT", "访问复核已关闭", http_status=409)

    snapshot_keys = {str(item.get("itemKey") or "") for item in (review.get("items") or [])}
    decision_keys = {str(item.get("itemKey") or "") for item in decisions}
    if snapshot_keys != decision_keys:
        missing = sorted(snapshot_keys - decision_keys)
        unknown = sorted(decision_keys - snapshot_keys)
        raise AppException(
            "ACCESS_REVIEW_DECISION_SET_MISMATCH",
            "关闭访问复核必须对冻结快照中的每一项明确 KEEP 或 REVOKE",
            http_status=409,
            details={"missingItemKeys": missing, "unknownItemKeys": unknown},
        )
    return _runtime.close_access_review(review_id, payload, actor=actor)


def terminate_record(
    config_type: str,
    record_id: str,
    *,
    tenant_id: int,
    expected_version: int,
    reason: str,
    actor: dict,
) -> dict:
    if config_type == _runtime.SUPPORT:
        rows = [
            item for item in _runtime.list_records(_runtime.SUPPORT, tenant_id=tenant_id)
            if str(item.get("id")) == str(record_id)
        ]
        if not rows:
            raise AppException("DATA_NOT_FOUND", "受控协助会话不存在", http_status=404)
        owner = str(rows[0].get("operatorUserId") or "")
        actor_id = str(actor.get("userId") or "")
        if owner and owner != actor_id:
            _runtime.assert_platform_capability(actor, "access.manage")
    return _runtime.terminate_record(
        config_type,
        record_id,
        tenant_id=tenant_id,
        expected_version=expected_version,
        reason=reason,
        actor=actor,
    )


for _name in dir(_runtime):
    if _name.startswith("_") or _name in globals():
        continue
    globals()[_name] = getattr(_runtime, _name)


def __getattr__(name: str):
    return getattr(_runtime, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_runtime)))
