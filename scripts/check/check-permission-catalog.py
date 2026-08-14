#!/usr/bin/env python3
"""B3 authoritative permission reconciliation gate (stdlib only)."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "shared/contracts/permission-catalog.json"
PY_ROOTS = [ROOT / "backend/app"]
TEXT_ROOTS = [ROOT / "frontend", ROOT / "enterprise-portal", ROOT / "student-portal", ROOT / "miniapp"]
GATE_CALLS = {"require_permission", "require_any_permission", "has_permission", "enforce_permission", "assert_platform_permission", "require_platform_permission"}
E_REQUIRED = {
    "internship.recruitment.view", "internship.recruitment.manage", "internship.recruitment.invite", "internship.recruitment.close",
    "enterprise.internship.company.view", "enterprise.internship.company.edit",
    "enterprise.internship.position.view", "enterprise.internship.position.manage", "enterprise.internship.position.submit",
    "enterprise.internship.application.view", "enterprise.internship.application.decide",
    "enterprise.internship.student.view", "enterprise.internship.eval.submit",
}
FRONT_RE = re.compile(r"(?:permissionKey|permissionCode)\s*[:=]\s*['\"]([A-Za-z0-9_.*-]+)['\"]")


def load_catalog():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    exact = {item["permissionCode"]: item for item in payload.get("entries") or []}
    patterns = [item["pattern"] for item in payload.get("legacyPatternCoverage") or []]
    return payload, exact, patterns


def covered_by_pattern(code: str, pattern: str) -> bool:
    # The literal RBAC wildcard is a B8 debt item, not a catch-all Catalog rule.
    if pattern == "*":
        return code == "*"
    if pattern.endswith(".*"):
        return code.startswith(pattern[:-1])
    return code == pattern


def python_usage():
    used = []
    creators = []
    for root in PY_ROOTS:
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            rel = path.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if fn in GATE_CALLS:
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            used.append({"permissionCode": arg.value, "file": rel, "line": node.lineno, "source": fn})
                elif fn in {"assert_platform_capability", "require_platform_capability"} and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    used.append({"permissionCode": f"platform.{node.args[0].value}", "file": rel, "line": node.lineno, "source": fn})
                if fn == "Permission":
                    creators.append({"file": rel, "line": node.lineno})
    return used, creators


def frontend_usage():
    out = []
    for root in TEXT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".js", ".ts", ".vue", ".jsx", ".tsx"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in FRONT_RE.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                out.append({"permissionCode": match.group(1), "file": path.relative_to(ROOT).as_posix(), "line": line, "source": "frontend.permissionKey"})
    return out


def _is_frontend_ui_action(item: dict) -> bool:
    """Bare frontend keys are UI action locators, never RBAC permissionCode.

    Canonical permissions are namespaced dotted codes. The literal '*' is
    separately tracked as B8 wildcard debt and therefore excluded here.
    """
    code = str(item.get("permissionCode") or "")
    return item.get("source") == "frontend.permissionKey" and code != "*" and "." not in code


def _emit_error(item: dict, message: str) -> None:
    path = str(item.get("file") or "shared/contracts/permission-catalog.json")
    line = int(item.get("line") or 1)
    safe = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error file={path},line={line}::{safe}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-legacy", action="store_true", help="B8: legacy-pattern usage becomes RED")
    parser.add_argument("--write")
    args = parser.parse_args()
    payload, exact, patterns = load_catalog()
    used, creators = python_usage()
    used.extend(frontend_usage())
    rows = []
    for item in used:
        code = item["permissionCode"]
        if _is_frontend_ui_action(item):
            status = "UI_ACTION_NOT_PERMISSION"
        elif code in exact:
            status = "DEFINED_AND_USED"
        elif any(covered_by_pattern(code, pattern) for pattern in patterns):
            status = "USED_LEGACY_PATTERN"
        else:
            status = "USED_UNDEFINED"
        rows.append({**item, "status": status})
    undefined = [item for item in rows if item["status"] == "USED_UNDEFINED"]
    legacy = [item for item in rows if item["status"] == "USED_LEGACY_PATTERN"]
    ui_actions = [item for item in rows if item["status"] == "UI_ACTION_NOT_PERMISSION"]
    missing_e = sorted(E_REQUIRED - set(exact))
    bad_enterprise = sorted(code for code, meta in exact.items() if code.startswith("enterprise.internship.") and (meta.get("moduleKey") != "internship" or meta.get("plane") != "TENANT" or meta.get("tenantAssignable") or meta.get("customRoleAssignable")))
    bad_e_module = sorted(code for code in E_REQUIRED if code in exact and exact[code].get("moduleKey") != "internship")
    report = {
        "summary": {
            "used": len(rows),
            "usedUndefined": len(undefined),
            "usedLegacyPattern": len(legacy),
            "uiActionNotPermission": len(ui_actions),
            "catalogExact": len(exact),
            "permissionCreators": len(creators),
        },
        "usedUndefined": undefined,
        "usedLegacyPattern": legacy,
        "uiActionNotPermission": ui_actions,
        "permissionCreators": creators,
        "missingESeries": missing_e,
        "badEnterpriseAssignmentPolicy": bad_enterprise,
        "badESeriesModuleKey": bad_e_module,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.write:
        target = ROOT / args.write
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded, encoding="utf-8")

    for item in undefined:
        _emit_error(item, f"USED_UNDEFINED permissionCode={item['permissionCode']} source={item['source']}")
    for code in missing_e:
        _emit_error({}, f"MISSING_E_SERIES permissionCode={code}")
    for code in bad_enterprise:
        _emit_error({}, f"BAD_ENTERPRISE_ASSIGNMENT_POLICY permissionCode={code}")
    for code in bad_e_module:
        _emit_error({}, f"BAD_E_SERIES_MODULE_KEY permissionCode={code}")
    if args.strict_legacy:
        for item in legacy:
            _emit_error(item, f"B8_USED_LEGACY_PATTERN permissionCode={item['permissionCode']}")

    if undefined or missing_e or bad_enterprise or bad_e_module or (args.strict_legacy and legacy):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
