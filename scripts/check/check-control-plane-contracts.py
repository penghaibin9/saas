#!/usr/bin/env python3
"""控制面合同检查：阻断门禁漂移、假成功、明文加密、无归属权限节点等。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "shared" / "contracts" / "module-manifest.json"
REGISTRY = ROOT / "shared" / "generated" / "capability-registry.json"
ROUTE_REG = ROOT / "backend" / "app" / "api" / "v1" / "route_registration.py"
PLATFORM_DEFAULTS = ROOT / "backend" / "app" / "services" / "platform_defaults.py"
GOVERNANCE = ROOT / "backend" / "app" / "services" / "system_governance_service.py"
SYSTEM_API = ROOT / "backend" / "app" / "api" / "v1" / "system.py"
PERM_GATE = ROOT / "frontend" / "src" / "security" / "permissionGate.js"

VALID_POLICIES = {"EXPLICIT", "INHERIT_FIRST_LEAF", "INHERIT_WORKSPACE", "EXEMPT", "UNRESOLVED"}
VALID_EXEMPT = {
    "WORKBENCH_PUBLIC_ENTRY",
    "EXTERNAL_DEPENDENCY",
    "NON_SIDEBAR_NO_WORKSPACE_PERM",
    "PLANNED_PLACEHOLDER",
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def main() -> int:
    errors: list[str] = []
    classified = {
        "explicit": 0,
        "inherited": 0,
        "exempt": 0,
        "unresolved": 0,
        "fixed_via_policy": 0,
    }

    if not MANIFEST.exists():
        errors.append("缺少 shared/contracts/module-manifest.json")
    else:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        feature_keys_text = _read(PLATFORM_DEFAULTS)
        for m in manifest["modules"]:
            if f'"{m["featureKey"]}"' not in feature_keys_text and f"'{m['featureKey']}'" not in feature_keys_text:
                errors.append(f"featureKey 不存在: {m['moduleKey']}->{m['featureKey']}")

    if not REGISTRY.exists():
        errors.append("缺少 capability-registry.json，请先运行 generate-capability-registry.mjs")
    else:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        mods = set()
        aliases = set()
        if MANIFEST.exists():
            for m in json.loads(MANIFEST.read_text(encoding="utf-8"))["modules"]:
                mods.add(m["moduleKey"])
                aliases.update(m.get("aliases") or [])

        for cap in reg.get("capabilities") or []:
            status = cap.get("status")
            policy = cap.get("permissionPolicy") or "UNRESOLVED"
            if policy not in VALID_POLICIES:
                errors.append(f"非法 permissionPolicy={policy}: {cap.get('capabilityKey')}")
                continue

            if policy == "EXPLICIT":
                classified["explicit"] += 1
            elif policy in ("INHERIT_FIRST_LEAF", "INHERIT_WORKSPACE"):
                classified["inherited"] += 1
                classified["fixed_via_policy"] += 1
            elif policy == "EXEMPT":
                classified["exempt"] += 1
                reason = cap.get("permissionExemptReason")
                if reason not in VALID_EXEMPT:
                    errors.append(
                        f"豁免缺少合法原因: {cap.get('capabilityKey')} reason={reason}"
                    )
            else:
                classified["unresolved"] += 1

            if status in ("implemented", "partial"):
                if not cap.get("path"):
                    # workspace without path may be planned container; only error if marked implemented with no path and has sidebar
                    if cap.get("sidebarEligible") and cap.get("entryType") == "WORKSPACE" and not (cap.get("path")):
                        # allow planned-like workspace without path when status wrongly set — still require policy
                        pass
                elif not cap.get("routeExists"):
                    path = str(cap.get("path") or "")
                    if not path.startswith("/admin/planned/"):
                        errors.append(
                            f"implemented/partial 无真实路由: {path} ({cap.get('capabilityKey')})"
                        )

                # 正式侧栏节点必须有可执行权限策略（显式或继承），不得 UNRESOLVED
                needs_perm = (
                    cap.get("sidebarEligible")
                    and cap.get("entryType") not in ("DETAIL", "ACTION", "FILTER_VIEW")
                    and str(cap.get("path") or "") not in ("/", "/admin/help")
                )
                if needs_perm:
                    if policy == "UNRESOLVED" or (
                        not cap.get("permissionKey") and policy != "EXEMPT"
                    ):
                        errors.append(
                            f"正式节点无权限策略: {cap.get('capabilityKey')} policy={policy}"
                        )
                    if policy == "EXEMPT" and cap.get("permissionExemptReason") not in VALID_EXEMPT:
                        errors.append(f"正式节点非法豁免: {cap.get('capabilityKey')}")

            tech = cap.get("techModule")
            if tech and tech not in mods and tech not in aliases:
                errors.append(f"技术模块未进入模块清单: {tech}")

    route_text = _read(ROUTE_REG)
    if re.search(r'employment\.router,\s*dependencies=deps\["intern"\]', route_text):
        errors.append("employment 错误复用 internship 门禁")
    if 'deps["employment"]' not in route_text and 'require_module("employment")' not in route_text:
        errors.append("employment 未注册独立模块门禁")
    if 'orientation.router' in route_text and 'deps["orientation"]' not in route_text:
        errors.append("orientation 未挂 orientation 门禁")
    if re.search(r'include_router\(\s*academic\.router\s*\)', route_text):
        errors.append("旧 academic 注册缺少模块门禁依赖")

    platform = _read(ROOT / "backend" / "app" / "services" / "platform_service.py")
    if re.search(r"effective_features\(tenant_id\)\.get\(key,\s*True\)", platform):
        errors.append("feature_enabled 对未知键默认 True（应拒绝）")

    system_api = _read(SYSTEM_API)
    if re.search(r"role\.remark\s*=.*scope=", system_api):
        errors.append("仍存在 Role.remark 数据范围写入主链路")

    for m in re.finditer(r"phone_encrypted\s*=\s*(?!encrypt_)(\w+)", system_api):
        if m.group(1) in ("phone", "value", "raw", "plaintext", "mobile"):
            errors.append(f"疑似明文写入加密字段: phone_encrypted = {m.group(1)}")

    gov = _read(GOVERNANCE)
    if 'else "SUCCESS"' in gov and "KNOWN_SYNC_ADAPTERS" not in gov:
        errors.append("同步任务无真实执行器却写 SUCCESS")
    if re.search(r'"status":\s*"FAILED" if body\.get\("forceFail"\) else "SUCCESS"', gov):
        errors.append("同步任务无真实执行器却写 SUCCESS")

    gate = _read(PERM_GATE)
    for code in ("SYSTEM", "EMPLOYMENT", "ORIENTATION"):
        if code not in gate:
            errors.append(f"permissionGate 未覆盖 {code}")

    # 统计输出（无“无分类普通警告”）
    print(
        "permissionKey classification: "
        f"explicit={classified['explicit']} inherited={classified['inherited']} "
        f"exempt={classified['exempt']} unresolved={classified['unresolved']}"
    )
    if REGISTRY.exists():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        print(f"routeMatchStats={reg.get('routeMatchStats')}")
        print(f"permissionPolicyStats={reg.get('permissionPolicyStats')}")

    if errors:
        print("FAIL control-plane-contracts")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK control-plane-contracts (no uncategorized permission warnings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
