"""Authoritative Permission Catalog reader and assignment policy."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.exceptions import AppException

_CATALOG = Path(__file__).resolve().parents[3] / "shared" / "contracts" / "permission-catalog.json"


@lru_cache(maxsize=1)
def load_permission_catalog() -> dict:
    payload = json.loads(_CATALOG.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []
    codes = [str(item.get("permissionCode") or "") for item in entries]
    if len(codes) != len(set(codes)) or any(not code for code in codes):
        raise RuntimeError("permission-catalog.json contains duplicate/empty permissionCode")
    payload["_byCode"] = {item["permissionCode"]: item for item in entries}
    return payload


def permission_meta(code: str) -> dict | None:
    return load_permission_catalog()["_byCode"].get(str(code or "").strip())


def _legacy_pattern_for(code: str) -> str | None:
    value = str(code or "").strip()
    for item in load_permission_catalog().get("legacyPatternCoverage") or []:
        pattern = str(item.get("pattern") or "").strip()
        if pattern == "*":
            return pattern
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

    Exact catalog entries are authoritative immediately.  Legacy permission
    families stay temporarily assignable only when explicitly covered by the
    catalog's B8 retirement ledger; completely undefined codes fail closed.
    """
    denied: list[str] = []
    unknown: list[str] = []
    legacy: list[dict] = []
    for code in sorted({str(value or "").strip() for value in (codes or []) if str(value or "").strip()}):
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
