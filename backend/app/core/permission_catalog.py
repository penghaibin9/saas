"""Authoritative Permission Catalog reader and assignment policy."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.exceptions import AppException

_ROOT = Path(__file__).resolve().parents[3] / "shared" / "contracts"
_CATALOG = _ROOT / "permission-catalog.json"
_B8_CONCRETE = _ROOT / "permission-catalog-b8-concrete.json"


def _materialize_b8_entry(code: str, extension: dict) -> dict:
    """Materialize audited B8 concrete inventory into normal Catalog metadata.

    These codes were already assignable through legacyPatternCoverage before
    B8; exact materialization preserves that assignment surface while making
    every concrete code reviewable and shadowable. Enterprise permissions are
    not in this extension and keep their explicit non-assignable metadata.
    """
    parts = str(code or "").split(".")
    prefix = parts[0] if parts else ""
    module_key = (extension.get("prefixModuleMap") or {}).get(prefix)
    if not module_key:
        raise RuntimeError(f"B8 concrete permission has unmapped prefix: {code}")
    policy = extension.get("riskPolicy") or {}
    lowered = [part.lower() for part in parts[1:]]
    critical = {str(v).lower() for v in policy.get("criticalTokens") or []}
    reason = {str(v).lower() for v in policy.get("reasonTokens") or []}
    read_suffixes = {str(v).lower() for v in policy.get("readSuffixes") or []}
    if any(token in critical for token in lowered):
        risk = "CRITICAL"
    elif any(token in reason for token in lowered):
        risk = "HIGH"
    elif lowered and lowered[-1] in read_suffixes:
        risk = "LOW"
    else:
        risk = "MEDIUM"
    requires_reason = any(token in reason for token in lowered)
    defaults = extension.get("defaults") or {}
    return {
        "permissionCode": code,
        "label": code,
        "plane": defaults.get("plane", "TENANT"),
        "moduleKey": module_key,
        "featureKey": parts[1] if len(parts) > 1 else prefix,
        "riskLevel": risk,
        "tenantAssignable": bool(defaults.get("tenantAssignable", True)),
        "customRoleAssignable": bool(defaults.get("customRoleAssignable", True)),
        "requiresReason": requires_reason,
        "lifecycle": defaults.get("lifecycle", "ACTIVE"),
        "catalogSource": "B8_CONCRETE_CUTOVER",
    }


@lru_cache(maxsize=1)
def load_permission_catalog() -> dict:
    payload = json.loads(_CATALOG.read_text(encoding="utf-8"))
    extension = json.loads(_B8_CONCRETE.read_text(encoding="utf-8"))
    entries = list(payload.get("entries") or [])
    entries.extend(_materialize_b8_entry(str(code), extension) for code in extension.get("entries") or [])
    codes = [str(item.get("permissionCode") or "") for item in entries]
    if len(codes) != len(set(codes)) or any(not code for code in codes):
        raise RuntimeError("permission catalog contains duplicate/empty permissionCode")
    payload["entries"] = entries
    payload["b8ConcreteCatalog"] = {
        "card": extension.get("card"),
        "count": len(extension.get("entries") or []),
        "temporaryRuntimeProbeCodes": list(extension.get("temporaryRuntimeProbeCodes") or []),
    }
    payload["_byCode"] = {item["permissionCode"]: item for item in entries}
    return payload


def permission_meta(code: str) -> dict | None:
    return load_permission_catalog()["_byCode"].get(str(code or "").strip())


def runtime_wildcard_probe_codes() -> set[str]:
    return set(load_permission_catalog().get("b8ConcreteCatalog", {}).get("temporaryRuntimeProbeCodes") or [])


def _legacy_pattern_for(code: str) -> str | None:
    value = str(code or "").strip()
    for item in load_permission_catalog().get("legacyPatternCoverage") or []:
        pattern = str(item.get("pattern") or "").strip()
        if pattern == "*":
            return pattern if value == "*" else None
        if pattern.endswith(".*") and value.startswith(pattern[:-1]):
            return pattern
        if pattern == value:
            return pattern
    return None


def assert_active_catalog_permission(code: str) -> dict:
    meta = permission_meta(code)
    if meta is None or str(meta.get("lifecycle") or "").upper() != "ACTIVE":
        raise AppException(
            "PERMISSION_CATALOG_DRIFT", "权限未在权威 Catalog 中处于 ACTIVE",
            http_status=409, details={"permissionCode": code},
        )
    return meta


def assert_custom_role_assignable(codes, *, allow_legacy_patterns: bool = True) -> dict:
    """Enforce school Custom Role assignment policy.

    Exact catalog entries are authoritative. During B8 only the separately
    tracked runtime wildcard probe may remain legacy in code; it is never a
    valid Custom Role permission. New concrete permission codes must be added
    to the Catalog instead of silently inheriting a family wildcard.
    """
    denied: list[str] = []
    unknown: list[str] = []
    legacy: list[dict] = []
    probes = runtime_wildcard_probe_codes()
    for code in sorted({str(value or "").strip() for value in (codes or []) if str(value or "").strip()}):
        if code in probes:
            denied.append(code)
            continue
        meta = permission_meta(code)
        if meta is None:
            pattern = _legacy_pattern_for(code) if allow_legacy_patterns else None
            if pattern:
                legacy.append({"permissionCode": code, "pattern": pattern})
            else:
                unknown.append(code)
            continue
        if (
            str(meta.get("lifecycle") or "").upper() != "ACTIVE"
            or not bool(meta.get("tenantAssignable"))
            or not bool(meta.get("customRoleAssignable"))
            or meta.get("plane") != "TENANT"
        ):
            denied.append(code)
    if unknown:
        raise AppException(
            "PERMISSION_CATALOG_DRIFT",
            "自定义角色包含未在权威 Catalog 定义、也未登记为 B8 过渡权限的权限",
            http_status=409,
            details={"permissionCodes": unknown[:50]},
        )
    if denied:
        raise AppException(
            "PERMISSION_NOT_ASSIGNABLE",
            "这些权限不能由学校 Custom Role 分配",
            http_status=403,
            details={"permissionCodes": denied[:50]},
        )
    return {"legacyAssignments": legacy, "legacyCount": len(legacy)}


def enterprise_permission_codes() -> set[str]:
    return {
        code
        for code, meta in load_permission_catalog()["_byCode"].items()
        if code.startswith("enterprise.") and meta.get("moduleKey") == "internship"
    }
