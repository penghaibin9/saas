"""Code-first authority projections and governed shared-config writes.

This module is deliberately outside the byte-frozen platform bundle. It owns
read-only authority projections used by exact route replacements during W1-W4
and the only new governed RULES/BRAND writers introduced by W4.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.services import platform_defaults as D


def config_snapshot(tenant_id: int, config_type: str, key: str = "-") -> dict:
    """Return one PlatformConfig payload together with its optimistic-lock version."""
    from app.models import PlatformConfig

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == int(tenant_id),
            PlatformConfig.config_type == str(config_type),
            PlatformConfig.config_key == str(key),
            PlatformConfig.is_deleted.is_(False),
        )).first()
        return {
            "exists": row is not None,
            "payload": dict(row.config_json or {}) if row else {},
            "version": int(row.version or 1) if row else 0,
        }
    finally:
        db.close()


def _required_version(value, *, label: str) -> int:
    from app.core.exceptions import AppException

    if value is None:
        raise AppException("VALIDATION_ERROR", f"{label}必须提供 expectedVersion", http_status=422)
    try:
        version = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label} expectedVersion 必须为整数", http_status=422) from None
    if version < 0:
        raise AppException("VALIDATION_ERROR", f"{label} expectedVersion 不能为负数", http_status=422)
    return version


def _required_reason(value, *, label: str) -> str:
    from app.core.exceptions import AppException

    reason = str(value or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", f"{label}变更原因至少5个字符", http_status=422)
    return reason


def features_projection(tenant_id: int) -> dict:
    """Expose commercial entitlement plus any grandfathered legacy override."""
    from app.services import platform_service

    tenant = platform_service.get_tenant(int(tenant_id))
    meta = platform_service.tenant_meta(int(tenant_id))
    package = platform_service.get_package(str(meta.get("packageCode") or "professional"))
    package_merged = {**D.DEFAULT_FEATURES, **(package.get("features") or {})}
    package_features = {key: bool(package_merged.get(key, False)) for key in D.FEATURE_KEYS}
    legacy = config_snapshot(int(tenant_id), "FEATURES")
    effective = platform_service.effective_features(int(tenant_id))
    drift = {
        key: {"package": package_features.get(key, False), "legacy": bool(value)}
        for key, value in legacy["payload"].items()
        if key in D.FEATURE_KEYS and bool(value) != bool(package_features.get(key, False))
    }
    if legacy["payload"]:
        authority_source = "LEGACY_OVERRIDE_READ_ONLY"
    elif meta.get("lastCommercialOrderNo"):
        authority_source = "PAID_ORDER"
    elif str(meta.get("lastCommercialAuthority") or "").upper() == "CONTROLLED_EXCEPTION":
        authority_source = "CONTROLLED_EXCEPTION"
    else:
        authority_source = "PACKAGE"
    return {
        "tenantId": str(tenant_id),
        "tenantName": tenant.get("tenantName"),
        "packageCode": package.get("packageCode"),
        "features": effective,
        "packageFeatures": package_features,
        "authoritySource": authority_source,
        "commercialOrderNo": meta.get("lastCommercialOrderNo") or None,
        "legacyOverride": legacy["payload"],
        "legacyOverrideVersion": legacy["version"],
        "legacyOverrideReadOnly": bool(legacy["payload"]),
        "legacyDrift": drift,
        "repairRequired": bool(drift),
    }


def _workflow_row(definition, nodes: list) -> dict:
    return {
        "workflowCode": definition.workflow_code,
        "workflowName": definition.workflow_name,
        "enabled": definition.status == "ENABLED",
        "needApproval": bool(nodes),
        "approverRoleCodes": [node.approver_role_code for node in nodes],
        "ccRoleCodes": definition.cc_role_codes_json or [],
        "timeoutHours": definition.timeout_hours,
        "allowTransfer": definition.allow_transfer,
        "allowReject": definition.allow_reject,
        "allowWithdraw": definition.allow_withdraw,
        "policyConfirmed": definition.policy_confirmed,
        "definitionVersion": definition.definition_version,
        "rowVersion": int(definition.version or 0),
        "status": definition.status,
    }


def workflow_projection(tenant_id: int) -> dict:
    """Project WorkflowDefinition as the only runtime workflow authority."""
    from app.models import WorkflowDefinition, WorkflowNodeDefinition
    from app.services import platform_service

    platform_service.get_tenant(int(tenant_id))
    legacy = config_snapshot(int(tenant_id), "WORKFLOWS")
    db = get_sessionmaker()()
    try:
        definitions = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == int(tenant_id),
            WorkflowDefinition.is_deleted.is_(False),
        ).order_by(WorkflowDefinition.workflow_code)).all()
        ids = [int(row.id) for row in definitions]
        nodes_by_definition: dict[int, list] = {value: [] for value in ids}
        if ids:
            nodes = db.scalars(select(WorkflowNodeDefinition).where(
                WorkflowNodeDefinition.tenant_id == int(tenant_id),
                WorkflowNodeDefinition.workflow_definition_id.in_(ids),
                WorkflowNodeDefinition.is_deleted.is_(False),
                WorkflowNodeDefinition.status == "ACTIVE",
            ).order_by(WorkflowNodeDefinition.workflow_definition_id, WorkflowNodeDefinition.sequence_no)).all()
            for node in nodes:
                nodes_by_definition.setdefault(int(node.workflow_definition_id), []).append(node)
        workflows = {
            row.workflow_code: _workflow_row(row, nodes_by_definition.get(int(row.id), []))
            for row in definitions
        }
    finally:
        db.close()

    drift = []
    legacy_rows = dict(legacy["payload"] or {})
    for code in sorted(set(workflows) | set(legacy_rows)):
        canonical = workflows.get(code)
        old = legacy_rows.get(code) if isinstance(legacy_rows.get(code), dict) else None
        if canonical is None:
            state = "CONFIG_ONLY"
        elif old is None:
            state = "DEFINITION_ONLY"
        else:
            comparable = {
                "enabled": canonical.get("enabled"),
                "needApproval": canonical.get("needApproval"),
                "timeoutHours": canonical.get("timeoutHours"),
                "approverRoleCodes": canonical.get("approverRoleCodes") or [],
            }
            old_comparable = {key: old.get(key) for key in comparable if key in old}
            state = "MATCH" if all(old_comparable[key] == comparable[key] for key in old_comparable) else "CONFLICT"
        drift.append({"workflowCode": code, "state": state})

    return {
        "tenantId": str(tenant_id),
        "authority": "WORKFLOW_DEFINITION",
        "workflows": workflows,
        "items": list(workflows.values()),
        "legacyOverride": legacy_rows,
        "legacyOverrideVersion": legacy["version"],
        "legacyOverrideReadOnly": bool(legacy_rows),
        "drift": drift,
        "writeSurface": "/admin/system/workflow-governance",
    }


def rules_projection(tenant_id: int) -> dict:
    from app.services import platform_service

    platform_service.get_tenant(int(tenant_id))
    snapshot = config_snapshot(int(tenant_id), "RULES")
    return {
        "tenantId": str(tenant_id),
        "rules": platform_service.effective_rules(int(tenant_id)),
        "override": snapshot["payload"],
        "overrideVersion": snapshot["version"],
    }


def update_rules(tenant_id: int, *, rules: dict, expected_version, reason: str) -> dict:
    from app.services import audit_log, platform_service

    tid = int(tenant_id)
    platform_service.get_tenant(tid)
    version = _required_version(expected_version, label="规则")
    reason_text = _required_reason(reason, label="规则")
    patch = platform_service.validate_rules(dict(rules or {}))
    before = config_snapshot(tid, "RULES")
    merged = dict(before["payload"])
    for group, values in patch.items():
        merged.setdefault(group, {}).update(values)
    platform_service.put_config_json(
        tid, "RULES", "-", merged, expected_version=version,
    )
    after = config_snapshot(tid, "RULES")
    audit_log.record(
        "PLATFORM_RULES_UPDATE",
        f"tenant:{tid}",
        detail={
            "groups": sorted(patch),
            "reason": reason_text,
            "expectedVersion": version,
            "currentVersion": after["version"],
            "before": before["payload"],
            "after": patch,
        },
        result="SUCCESS",
        tenant_id=tid,
    )
    return {
        "tenantId": str(tid),
        "rules": platform_service.effective_rules(tid),
        "override": after["payload"],
        "overrideVersion": after["version"],
    }


def brand_projection(tenant_id: int) -> dict:
    from app.services import platform_service

    platform_service.get_tenant(int(tenant_id))
    snapshot = config_snapshot(int(tenant_id), "BRAND")
    return {
        "tenantId": str(tenant_id),
        "brand": platform_service.effective_brand(int(tenant_id)),
        "override": snapshot["payload"],
        "overrideVersion": snapshot["version"],
    }


def update_brand(tenant_id: int, *, brand: dict, expected_version, reason: str) -> dict:
    from app.core.exceptions import AppException
    from app.services import audit_log, platform_service

    tid = int(tenant_id)
    platform_service.get_tenant(tid)
    version = _required_version(expected_version, label="品牌")
    reason_text = _required_reason(reason, label="品牌")
    allow = set(D.DEFAULT_BRAND)
    patch = {key: str(value) for key, value in dict(brand or {}).items() if key in allow}
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可更新的品牌字段", http_status=422)
    before = config_snapshot(tid, "BRAND")
    merged = {**before["payload"], **patch}
    platform_service.put_config_json(
        tid, "BRAND", "-", merged, expected_version=version,
    )
    after = config_snapshot(tid, "BRAND")
    audit_log.record(
        "PLATFORM_BRAND_UPDATE",
        f"tenant:{tid}",
        detail={
            "keys": sorted(patch),
            "reason": reason_text,
            "expectedVersion": version,
            "currentVersion": after["version"],
            "before": before["payload"],
            "after": patch,
        },
        result="SUCCESS",
        tenant_id=tid,
    )
    return {
        "tenantId": str(tid),
        "brand": platform_service.effective_brand(tid),
        "override": after["payload"],
        "overrideVersion": after["version"],
    }
