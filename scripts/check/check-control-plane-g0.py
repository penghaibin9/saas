#!/usr/bin/env python3
"""G0 Control Plane source-truth scanner.

Pure-stdlib by design: it can run before backend dependencies are installed.
It never mutates repository state.  The scanner reports route, permission and
Alembic graph facts used by the Control Plane Collision Ledger.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "app" / "api" / "v1"
ALEMBIC_ROOT = ROOT / "backend" / "alembic" / "versions"
BACKEND_ROOT = ROOT / "backend" / "app"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _router_prefix(tree: ast.Module) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else getattr(node, "target", None)
        value = node.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            continue
        func = value.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name != "APIRouter":
            continue
        prefix = ""
        for kw in value.keywords:
            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                prefix = kw.value.value
        out[target.id] = prefix
    return out


def route_inventory() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for path in sorted(API_ROOT.glob("*.py")):
        try:
            tree = ast.parse(_source(path), filename=str(path))
        except SyntaxError:
            continue
        prefixes = _router_prefix(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                    continue
                if deco.func.attr.lower() not in HTTP_METHODS or not isinstance(deco.func.value, ast.Name):
                    continue
                router_name = deco.func.value.id
                if not deco.args or not isinstance(deco.args[0], ast.Constant) or not isinstance(deco.args[0].value, str):
                    continue
                local_path = deco.args[0].value
                prefix = prefixes.get(router_name, "")
                full_path = f"{prefix}{local_path}" or "/"
                routes.append({
                    "method": deco.func.attr.upper(),
                    "path": full_path,
                    "function": node.name,
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": node.lineno,
                })
    return sorted(routes, key=lambda item: (item["path"], item["method"], item["file"], item["line"]))


def permission_inventory() -> dict[str, Any]:
    used: list[dict[str, Any]] = []
    creators: list[dict[str, Any]] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(_source(path), filename=str(path))
        except SyntaxError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if fn in {"require_permission", "require_any_permission"}:
                codes = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
                for code in codes:
                    used.append({"permissionCode": code, "file": rel, "line": node.lineno, "gate": fn})
            if fn == "Permission":
                creators.append({"file": rel, "line": node.lineno})
    used.sort(key=lambda item: (item["permissionCode"], item["file"], item["line"]))
    creators.sort(key=lambda item: (item["file"], item["line"]))
    return {"used": used, "permissionCreators": creators}


def alembic_graph() -> dict[str, Any]:
    revisions: dict[str, dict[str, Any]] = {}
    referenced: set[str] = set()
    for path in sorted(ALEMBIC_ROOT.glob("*.py")):
        try:
            tree = ast.parse(_source(path), filename=str(path))
        except SyntaxError:
            continue
        values: dict[str, Any] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in {"revision", "down_revision"}:
                    values[node.targets[0].id] = _literal(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in {"revision", "down_revision"}:
                values[node.target.id] = _literal(node.value)
        revision = values.get("revision")
        if not isinstance(revision, str) or not revision:
            continue
        down = values.get("down_revision")
        downs = [down] if isinstance(down, str) else list(down or []) if isinstance(down, (tuple, list)) else []
        revisions[revision] = {"file": path.relative_to(ROOT).as_posix(), "downRevision": downs}
        referenced.update(str(value) for value in downs if value)
    heads = sorted(set(revisions) - referenced)
    missing = sorted(referenced - set(revisions))
    return {"heads": heads, "headCount": len(heads), "missingParents": missing, "revisionCount": len(revisions)}


def build_report() -> dict[str, Any]:
    routes = route_inventory()
    permissions = permission_inventory()
    platform_routes = [r for r in routes if r["path"].startswith("/platform")]
    system_routes = [r for r in routes if r["path"].startswith("/system")]
    mutations = [r for r in platform_routes if r["method"] in {"POST", "PUT", "PATCH", "DELETE"}]
    return {
        "alembic": alembic_graph(),
        "routes": {
            "system": system_routes,
            "platform": platform_routes,
            "platformMutations": mutations,
            "systemCount": len(system_routes),
            "platformCount": len(platform_routes),
            "platformMutationCount": len(mutations),
        },
        "permissions": permissions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        target = args.write if args.write.is_absolute() else ROOT / args.write
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if args.check:
        if report["alembic"]["headCount"] != 1 or report["alembic"]["missingParents"]:
            return 2
        if report["routes"]["platformCount"] == 0 or report["routes"]["systemCount"] == 0:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
