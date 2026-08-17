#!/usr/bin/env python3
"""Inventory System/Platform critical mutations without executing the app."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "backend/app/modules/system_admin/routers/system_bundle.py",
    ROOT / "backend/app/modules/platform/routers/platform_bundle.py",
]
WRITE = {"post", "put", "patch", "delete"}


def inventory(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                continue
            method = deco.func.attr.lower()
            if method not in WRITE or not deco.args or not isinstance(deco.args[0], ast.Constant):
                continue
            route_path = deco.args[0].value
            if not isinstance(route_path, str):
                continue
            end = getattr(node, "end_lineno", node.lineno)
            body = "\n".join(lines[node.lineno - 1:end])
            out.append({
                "method": method.upper(),
                "path": route_path,
                "function": node.name,
                "file": path.relative_to(ROOT).as_posix(),
                "signals": {
                    "expectedVersion": "expectedVersion" in body or "expected_version" in body,
                    "rowLock": "with_for_update" in body,
                    "reason": "reason" in body,
                    "idempotency": "Idempotency" in body or "idempotency" in body or "requestId" in body,
                    "criticalAudit": "record_critical_in_session" in body,
                    "cacheInvalidation": "invalidate" in body,
                },
            })
    return out


def main() -> int:
    rows = []
    for path in FILES:
        rows.extend(inventory(path))
    print(json.dumps({"mutations": rows, "count": len(rows)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
