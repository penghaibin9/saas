"""模块清单唯一事实源加载与键解析（对齐 shared/contracts/module-manifest.json）。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _ROOT / "shared" / "contracts" / "module-manifest.json"

# graduationDesign ↔ graduation；academicLegacy → academicAffairs
_FEATURE_ALIASES = {
    "graduationDesign": "graduation",
    "graduation": "graduation",
    "academicLegacy": "academicAffairs",
    "academic": "academicAffairs",
    "system": "systemAdmin",
}


@lru_cache(maxsize=1)
def load_module_manifest() -> dict:
    if not _MANIFEST.exists():
        return {"manifestVersion": "0", "schemaVersion": "0", "modules": []}
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def module_index() -> dict[str, dict]:
    data = load_module_manifest()
    idx: dict[str, dict] = {}
    for mod in data.get("modules") or []:
        idx[mod["moduleKey"]] = mod
        for alias in mod.get("aliases") or []:
            idx[alias] = mod
    return idx


def resolve_module(module_key: str) -> dict | None:
    key = str(module_key or "").strip()
    if not key:
        return None
    return module_index().get(key) or module_index().get(_FEATURE_ALIASES.get(key, key))


def resolve_feature_key(module_key: str) -> str | None:
    """门禁使用的商业功能键。未知模块返回 None（调用方应拒绝）。"""
    mapped = _FEATURE_ALIASES.get(module_key, module_key)
    mod = resolve_module(mapped) or resolve_module(module_key)
    if mod:
        return mod.get("featureKey")
    # 兼容历史直接传入 featureKey
    from app.services import platform_defaults as D
    if module_key in D.FEATURE_KEYS or mapped in D.FEATURE_KEYS:
        return mapped if mapped in D.FEATURE_KEYS else module_key
    return None


def known_feature_keys() -> set[str]:
    from app.services import platform_defaults as D
    return set(D.FEATURE_KEYS)


def all_module_keys() -> list[str]:
    return [m["moduleKey"] for m in load_module_manifest().get("modules") or []]
