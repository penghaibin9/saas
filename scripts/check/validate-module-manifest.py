#!/usr/bin/env python3
"""校验 shared/contracts/module-manifest.json：唯一性、依赖无环、路由前缀冲突、featureKey 存在。"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "shared" / "contracts" / "module-manifest.json"
SCHEMA_PATH = ROOT / "shared" / "contracts" / "module-manifest.schema.json"
PLATFORM_DEFAULTS = ROOT / "backend" / "app" / "services" / "platform_defaults.py"

REQUIRED_KEYS = {
    "workbench", "approval", "messages", "dataCenter", "studentProfile", "orientation",
    "campusService", "studentAffairs", "academicLegacy", "academicAffairs",
    "graduationDesign", "internship", "employment", "systemAdmin", "platform",
}


def _load_feature_keys() -> set[str]:
    text = PLATFORM_DEFAULTS.read_text(encoding="utf-8")
    keys: set[str] = set()
    in_list = False
    for line in text.splitlines():
        if line.startswith("FEATURE_KEYS"):
            in_list = True
            continue
        if in_list:
            if line.strip().startswith("]"):
                break
            for part in line.replace("[", "").replace("]", "").replace('"', "").split(","):
                part = part.strip().strip("'")
                if part:
                    keys.add(part)
    return keys


def _has_cycle(deps: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> bool:
        if node in visiting:
            stack.append(node)
            return True
        if node in visited:
            return False
        visiting.add(node)
        stack.append(node)
        for nxt in deps.get(node, []):
            if dfs(nxt):
                return True
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return False

    for key in deps:
        stack.clear()
        if dfs(key):
            return stack
    return None


def main() -> int:
    errors: list[str] = []
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not data.get("manifestVersion") or not data.get("schemaVersion"):
        errors.append("manifestVersion/schemaVersion 必填")
    modules = data.get("modules") or []
    if not isinstance(modules, list) or not modules:
        errors.append("modules 不能为空")
        print("\n".join(errors))
        return 1

    required_props = set(schema["properties"]["modules"]["items"]["required"])
    keys: list[str] = []
    feature_keys = _load_feature_keys()
    deps: dict[str, list[str]] = {}
    route_owners: dict[str, str] = {}
    api_owners: dict[str, str] = {}
    aliases: dict[str, str] = {}

    for mod in modules:
        missing = required_props - set(mod)
        if missing:
            errors.append(f"{mod.get('moduleKey')}: 缺少字段 {sorted(missing)}")
            continue
        mk = mod["moduleKey"]
        keys.append(mk)
        if mk in deps:
            errors.append(f"moduleKey 重复: {mk}")
        deps[mk] = list(mod.get("dependencies") or [])
        fk = mod["featureKey"]
        if fk not in feature_keys:
            errors.append(f"{mk}: featureKey={fk} 不在 platform_defaults.FEATURE_KEYS")
        for alias in mod.get("aliases") or []:
            if alias in aliases or alias in deps:
                errors.append(f"{mk}: alias 冲突 {alias}")
            aliases[alias] = mk
        for prefix in mod.get("frontendRoutePrefixes") or []:
            # "/" 允许 workbench 独占；其余前缀冲突才报错
            if prefix == "/":
                continue
            owner = route_owners.get(prefix)
            if owner and owner != mk:
                # 允许同 schoolGroup 共享前缀（如 approval 与 workbench 共享 /admin/approval）
                a = next((m for m in modules if m["moduleKey"] == owner), {})
                b = mod
                if a.get("schoolGroup") != b.get("schoolGroup"):
                    errors.append(f"前端路由前缀冲突: {prefix} ({owner} vs {mk})")
            else:
                route_owners[prefix] = mk
        for prefix in mod.get("backendApiPrefixes") or []:
            owner = api_owners.get(prefix)
            if owner and owner != mk:
                a = next((m for m in modules if m["moduleKey"] == owner), {})
                if a.get("schoolGroup") != mod.get("schoolGroup"):
                    errors.append(f"后端 API 前缀冲突: {prefix} ({owner} vs {mk})")
            else:
                api_owners[prefix] = mk

    missing_required = REQUIRED_KEYS - set(keys)
    if missing_required:
        errors.append(f"缺少必选模块: {sorted(missing_required)}")

    # 显式映射校验
    by_key = {m["moduleKey"]: m for m in modules}
    gd = by_key.get("graduationDesign") or {}
    if "graduation" not in (gd.get("aliases") or []) or gd.get("featureKey") != "graduation":
        errors.append("graduationDesign 必须 alias=graduation 且 featureKey=graduation")
    al = by_key.get("academicLegacy") or {}
    if al.get("featureKey") != "academicAffairs":
        errors.append("academicLegacy 必须 featureKey=academicAffairs")
    emp = by_key.get("employment") or {}
    if emp.get("featureKey") != "employment":
        errors.append("employment 必须使用独立 employment 功能键")

    for mk, dep_list in deps.items():
        for d in dep_list:
            if d not in deps and d not in aliases:
                errors.append(f"{mk}: 未知依赖 {d}")

    cycle = _has_cycle(deps)
    if cycle:
        errors.append(f"依赖成环: {' -> '.join(cycle)}")

    if errors:
        print("FAIL module-manifest")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK module-manifest modules={len(modules)} aliases={len(aliases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
