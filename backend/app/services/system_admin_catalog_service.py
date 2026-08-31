"""School Custom Role authoring projection.

The Permission Catalog is the permission authority. The generated navigation
contract supplies menu/workspace placement only; permissions without a menu
remain visible under an explicit advanced-capability section.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.permission_catalog import load_permission_catalog
from app.core.permissions import has_permission

_CONTRACT_ROOT = Path(__file__).resolve().parents[3] / "shared" / "contracts"
_NAVIGATION_CONTRACT = _CONTRACT_ROOT / "navigation-surface-contract.json"

_MODULE_LABELS = {
    "workbench": "工作台",
    "workflow": "审批与流程",
    "dataCenter": "数据中心",
    "student": "学生主档",
    "orientation": "数字迎新",
    "campusService": "校园服务",
    "studentAffairs": "学工中心",
    "academicAffairs": "教务中心",
    "graduationDesign": "毕业设计中心",
    "internship": "岗位实习中心",
    "employment": "就业服务",
    "systemAdmin": "系统管理",
}


@lru_cache(maxsize=1)
def _navigation_surfaces() -> tuple[dict, ...]:
    payload = json.loads(_NAVIGATION_CONTRACT.read_text(encoding="utf-8"))
    return tuple(payload.get("surfaces") or ())


def _assignable_catalog_entries() -> list[dict]:
    return [
        item for item in load_permission_catalog().get("entries") or []
        if item.get("plane") == "TENANT"
        and str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and bool(item.get("tenantAssignable"))
        and bool(item.get("customRoleAssignable"))
        and not str(item.get("permissionCode") or "").startswith(("platform.", "enterprise.", "system."))
    ]


def collect_concrete_permission_codes() -> set[str]:
    """Concrete catalog universe used only to expand legacy role patterns."""
    return {
        str(item["permissionCode"])
        for item in load_permission_catalog().get("entries") or []
        if item.get("plane") == "TENANT"
        and str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and not str(item.get("permissionCode") or "").startswith("enterprise.")
    }


def expand_permission_patterns(patterns: set[str] | list[str]) -> set[str]:
    patterns = set(patterns or [])
    universe = collect_concrete_permission_codes()
    if "*" in patterns:
        return set(universe)
    out: set[str] = set()
    for pattern in patterns:
        if pattern.endswith(".*"):
            prefix = pattern[:-1]
            out.update(code for code in universe if code.startswith(prefix) or code == pattern[:-2])
        elif pattern.startswith("*."):
            suffix = pattern[1:]
            out.update(code for code in universe if code.endswith(suffix))
        else:
            out.add(pattern)
    return out


def _permission_node(entry: dict, *, node_type: str, label: str | None = None) -> dict:
    code = str(entry["permissionCode"])
    return {
        "key": code,
        "label": label or entry.get("label") or code,
        "type": node_type,
        "permissionCode": code,
        "riskLevel": entry.get("riskLevel") or "MEDIUM",
        "requiresReason": bool(entry.get("requiresReason")),
        "children": [],
    }


def _build_permission_tree(entries: dict[str, dict]) -> list[dict]:
    assigned: set[str] = set()
    modules: dict[str, list[dict]] = {}
    navigated_codes = {
        code
        for surface in _navigation_surfaces()
        if not surface.get("platformOnly")
        and not surface.get("hidden")
        and not surface.get("disabled")
        and str(surface.get("status") or "") in {"implemented", "partial"}
        for code in surface.get("permissionCodes") or []
        if code in entries
    }

    for surface in _navigation_surfaces():
        if surface.get("platformOnly") or surface.get("hidden") or surface.get("disabled"):
            continue
        if str(surface.get("status") or "") not in {"implemented", "partial"}:
            continue
        codes = [code for code in surface.get("permissionCodes") or [] if code in entries and code not in assigned]
        if not codes:
            continue
        primary = surface.get("permissionKey") if surface.get("permissionKey") in codes else codes[0]
        menu = _permission_node(entries[primary], node_type="MENU", label=surface.get("label"))
        menu["surfaceKey"] = surface.get("surfaceKey")
        menu["path"] = surface.get("path")
        primary_entry = entries[primary]
        feature_actions = sorted(
            code for code, entry in entries.items()
            if code not in assigned
            and code not in navigated_codes
            and code not in codes
            and entry.get("moduleKey") == primary_entry.get("moduleKey")
            and entry.get("featureKey") == primary_entry.get("featureKey")
        )
        codes.extend(feature_actions)
        for code in codes:
            assigned.add(code)
            if code != primary:
                menu["children"].append(_permission_node(entries[code], node_type="BUTTON"))
        module_key = str(entries[primary].get("moduleKey") or surface.get("moduleKey") or "advanced")
        modules.setdefault(module_key, []).append(menu)

    for code in sorted(set(entries) - assigned):
        entry = entries[code]
        module_key = str(entry.get("moduleKey") or "advanced")
        node = _permission_node(entry, node_type="MENU")
        node["advanced"] = True
        node["reason"] = "合法后台能力没有常规菜单入口"
        modules.setdefault(module_key, []).append(node)

    return [
        {
            "key": f"mod-{module_key}",
            "label": _MODULE_LABELS.get(module_key, module_key),
            "type": "MODULE",
            "children": sorted(children, key=lambda item: (bool(item.get("advanced")), item["label"], item["key"])),
        }
        for module_key, children in sorted(modules.items(), key=lambda item: (_MODULE_LABELS.get(item[0], item[0]), item[0]))
        if children
    ]


def build_permission_tree(user: dict) -> list[dict]:
    """Build the complete operator-editable tree from Catalog + navigation."""
    entries = {
        str(item["permissionCode"]): item
        for item in _assignable_catalog_entries()
        if has_permission(user, str(item["permissionCode"]))
    }
    return _build_permission_tree(entries)


def visible_codes_from_tree(tree: list[dict]) -> set[str]:
    codes: set[str] = set()
    for module in tree or []:
        for menu in module.get("children") or []:
            codes.add(menu["key"])
            codes.update(button["key"] for button in menu.get("children") or [])
    return codes


def split_selection(permission_codes: list[str], tree: list[dict]) -> dict:
    menu_keys: set[str] = set()
    button_keys: set[str] = set()
    for module in tree or []:
        for menu in module.get("children") or []:
            menu_keys.add(menu["key"])
            button_keys.update(button["key"] for button in menu.get("children") or [])
    codes = [code for code in permission_codes or [] if code]
    return {
        "menuKeys": [code for code in codes if code in menu_keys],
        "buttonKeys": [code for code in codes if code in button_keys],
        "permissionCodes": codes,
    }


def _legacy_group_projection() -> list[dict]:
    """Preserve the historical read shape without restoring it as authority."""
    entries = {str(item["permissionCode"]): item for item in _assignable_catalog_entries()}
    return [
        {
            "key": module["key"],
            "label": module["label"],
            "menus": [
                {
                    "code": menu["key"],
                    "label": menu["label"],
                    "actions": [(child["key"], child["label"]) for child in menu.get("children") or []],
                }
                for menu in module.get("children") or []
            ],
        }
        for module in _build_permission_tree(entries)
    ]


# Compatibility export for older imports. This projection is generated from the
# authoritative catalog/navigation data and never drives authoring coverage.
SCHOOL_PERMISSION_GROUPS: list[dict] = _legacy_group_projection()
