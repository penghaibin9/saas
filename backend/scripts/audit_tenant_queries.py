"""Heuristically list business queries that need a tenant-isolation review.

This read-only scanner is intentionally conservative: it does not claim that a
candidate is exploitable.  It highlights direct Session.get calls and SQLAlchemy
SELECT/UPDATE/DELETE statements whose source statement does not visibly mention
tenant_id or a recognized tenant helper.  Run after every new module is added.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
EXCLUDED_PARTS = {"migrations", "platform_service.py", "tenant_context.py"}
SAFE_MARKERS = ("tenant_id", "_tid(", "current_tenant_id", "tenant_scope", "tenantId")


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="return non-zero when direct Session.get calls are found")
    return parser.parse_args()


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def main() -> int:
    args = _args()
    direct_gets: list[str] = []
    candidates: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            print(f"PARSE {path.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in {"get", "select", "update", "delete"}:
                continue
            start = max(0, node.lineno - 1)
            end = min(len(lines), getattr(node, "end_lineno", node.lineno) + 3)
            statement = " ".join(lines[start:end])
            location = f"{path.relative_to(ROOT)}:{node.lineno}"
            if (name == "get" and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id.lower() in {"db", "session"}):
                # Session.get(Model, id) never carries tenant_id itself.  The caller
                # must immediately re-check ownership or replace it with a scoped select.
                direct_gets.append(location)
            elif name in {"select", "update", "delete"} and not any(
                    marker in statement for marker in SAFE_MARKERS):
                candidates.append(location)

    print(f"direct_session_get={len(direct_gets)} query_review_candidates={len(candidates)}")
    for item in direct_gets:
        print("HIGH", item, "verify tenant ownership after Session.get")
    for item in candidates:
        print("REVIEW", item)
    return 1 if args.strict and direct_gets else 0


if __name__ == "__main__":
    raise SystemExit(main())
