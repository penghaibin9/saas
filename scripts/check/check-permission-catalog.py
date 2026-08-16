#!/usr/bin/env python3
"""B3/B8 authoritative permission reconciliation gate (stdlib only)."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "shared/contracts/permission-catalog.json"
B8_CONCRETE_PATH = ROOT / "shared/contracts/permission-catalog-b8-concrete.json"
B8_COMPATIBILITY_PATH = ROOT / "shared/contracts/permission-catalog-b8-compatibility.json"
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


def _compatibility_codes(payload: dict) -> list[str]:
    codes = [str(code or "").strip() for code in payload.get("entries") or []]
    if any(not code for code in codes) or len(codes) != len(set(codes)):
        raise RuntimeError("B8 compatibility catalog contains duplicate/empty permissionCode")
    forbidden = [
        code for code in codes
        if code == "*" or code.startswith("platform.") or code.startswith("enterprise.")
    ]
    if forbidden:
        raise RuntimeError(
            "B8 compatibility catalog contains forbidden permission plane: "
            + ",".join(sorted(forbidden)[:20])
        )
    return codes


def load_catalog():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    extension = json.loads(B8_CONCRETE_PATH.read_text(encoding="utf-8"))
    compatibility = json.loads(B8_COMPATIBILITY_PATH.read_text(encoding="utf-8"))
    exact = {item["permissionCode"]: item for item in payload.get("entries") or []}
    base_concrete = [str(code or "").strip() for code in extension.get("entries") or []]
    compatibility_codes = _compatibility_codes(compatibility)
    for code in [*base_concrete, *compatibility_codes]:
        if not code:
            raise RuntimeError("B8 concrete catalog contains empty permissionCode")
        if code in exact:
            raise RuntimeError(f"B8 concrete catalog duplicates permissionCode: {code}")
        exact[code] = {"permissionCode": code, **dict(extension.get("defaults") or {}), "catalogSource": "B8_CONCRETE_CUTOVER"}
    patterns = [item["pattern"] for item in payload.get("legacyPatternCoverage") or []]
    probes = set(extension.get("temporaryRuntimeProbeCodes") or [])
    return payload, exact, patterns, probes, extension, compatibility


def covered_by_pattern(code: str, pattern: str) -> bool:
    # The literal RBAC wildcard is a B8 debt item, not a catch-all Catalog rule.
    if pattern == "*":
        return code == "*"
    if pattern.endswith(".*"):
        return code.startswith(pattern[:-1])
    return code == pattern


def _literal_strings(node: ast.AST | None, constants: dict[str, tuple[str, ...]]) -> list[str]:
    """Resolve only reviewable static permission literals.

    B8 must see permission codes hidden behind simple module-level constants such
    as ``_ARCHIVE_MANAGE = \"academicAffairs.archive.manage\"``.  Deliberately
    do not evaluate calls, attributes, f-strings, imports or other runtime
    expressions; unresolved dynamic gates remain visible to separate source
    reviews instead of this checker pretending to know their value.
    """
    if node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        return list(constants.get(node.id, ()))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for child in node.elts:
            values.extend(_literal_strings(child, constants))
        return values
    return []


def _module_string_constants(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Collect simple module-level literal aliases used by permission gates."""
    constants: dict[str, tuple[str, ...]] = {}
    # A few passes let one constant alias another without evaluating arbitrary code.
    for _ in range(3):
        changed = False
        for node in tree.body:
            target: ast.Name | None = None
            value: ast.AST | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = node.targets[0]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target = node.target
                value = node.value
            if target is None:
                continue
            values = tuple(dict.fromkeys(_literal_strings(value, constants)))
            if values and constants.get(target.id) != values:
                constants[target.id] = values
                changed = True
        if not changed:
            break
    return constants


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
            constants = _module_string_constants(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if fn in GATE_CALLS:
                    for arg in node.args:
                        for code in _literal_strings(arg, constants):
                            used.append({"permissionCode": code, "file": rel, "line": node.lineno, "source": fn})
                elif fn in {"assert_platform_capability", "require_platform_capability"} and node.args:
                    for capability in _literal_strings(node.args[0], constants):
                        used.append({"permissionCode": f"platform.{capability}", "file": rel, "line": node.lineno, "source": fn})
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
    code = str(item.get("permissionCode") or "")
    return item.get("source") == "frontend.permissionKey" and code != "*" and "." not in code


def _emit_error(item: dict, message: str) -> None:
    path = str(item.get("file") or "shared/contracts/permission-catalog.json")
    line = int(item.get("line") or 1)
    safe = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error file={path},line={line}::{safe}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-legacy", action="store_true", help="B8: every concrete legacy-pattern usage becomes RED")
    parser.add_argument("--write")
    args = parser.parse_args()
    payload, exact, patterns, probes, extension, compatibility = load_catalog()
    used, creators = python_usage()
    used.extend(frontend_usage())
    rows = []
    for item in used:
        code = item["permissionCode"]
        if _is_frontend_ui_action(item):
            status = "UI_ACTION_NOT_PERMISSION"
        elif code in probes:
            status = "RUNTIME_WILDCARD_PROBE"
        elif code in exact:
            status = "DEFINED_AND_USED"
        elif any(covered_by_pattern(code, pattern) for pattern in patterns):
            status = "USED_LEGACY_PATTERN"
        else:
            status = "USED_UNDEFINED"
        rows.append({**item, "status": status})
    undefined = [item for item in rows if item["status"] == "USED_UNDEFINED"]
    legacy = [item for item in rows if item["status"] == "USED_LEGACY_PATTERN"]
    runtime_probes = [item for item in rows if item["status"] == "RUNTIME_WILDCARD_PROBE"]
    ui_actions = [item for item in rows if item["status"] == "UI_ACTION_NOT_PERMISSION"]
    missing_e = sorted(E_REQUIRED - set(exact))
    bad_enterprise = sorted(code for code, meta in exact.items() if code.startswith("enterprise.internship.") and (meta.get("moduleKey") != "internship" or meta.get("plane") != "TENANT" or meta.get("tenantAssignable") or meta.get("customRoleAssignable")))
    bad_e_module = sorted(code for code in E_REQUIRED if code in exact and exact[code].get("moduleKey") != "internship")
    base_concrete_entries = [str(code) for code in extension.get("entries") or []]
    compatibility_entries = _compatibility_codes(compatibility)
    report = {
        "summary": {
            "used": len(rows),
            "usedUndefined": len(undefined),
            "usedLegacyPattern": len(legacy),
            "runtimeWildcardProbe": len(runtime_probes),
            "uiActionNotPermission": len(ui_actions),
            "catalogExact": len(exact),
            "b8ConcreteExact": len(base_concrete_entries) + len(compatibility_entries),
            "b8BaseConcreteExact": len(base_concrete_entries),
            "b8PostCutoverCompatibilityExact": len(compatibility_entries),
            "permissionCreators": len(creators),
        },
        "usedUndefined": undefined,
        "usedLegacyPattern": legacy,
        "runtimeWildcardProbe": runtime_probes,
        "uiActionNotPermission": ui_actions,
        "permissionCreators": creators,
        "postCutoverCompatibilityCodes": compatibility_entries,
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
