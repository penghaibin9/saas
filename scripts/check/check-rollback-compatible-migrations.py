#!/usr/bin/env python3
"""Reject newly changed Alembic upgrades that break previous-release compatibility.

Production rollback switches application bytes back to the previous release. New migrations must
therefore follow expand/contract: an N-1 application must continue to operate on the N schema until
N is accepted. Destructive contraction belongs in a later release after old code is retired.

Only migration files changed against ``ROLLBACK_BASE_REF`` are inspected, so historical migrations
are not grandfathered through an ever-growing whitelist. The workflow uses the PR base SHA or the
push-before SHA; local fallback is HEAD^.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS_PREFIX = "backend/alembic/versions/"
FORBIDDEN_CALLS = {"drop_table", "drop_column", "rename_table", "drop_constraint"}
DESTRUCTIVE_SQL = re.compile(r"\b(DROP|TRUNCATE|RENAME)\b", re.IGNORECASE)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def base_ref() -> str:
    value = (os.environ.get("ROLLBACK_BASE_REF") or "").strip()
    if value and set(value) != {"0"}:
        return value
    return git("rev-parse", "HEAD^")


def changed_migrations(base: str) -> list[Path]:
    names = git("diff", "--name-only", f"{base}...HEAD", "--", "backend/alembic/versions").splitlines()
    return [ROOT / name for name in names if name.startswith(VERSIONS_PREFIX) and name.endswith(".py") and (ROOT / name).is_file()]


def call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def constant_sql(node: ast.Call) -> str:
    values: list[str] = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            values.append(arg.value)
        elif isinstance(arg, ast.Call):
            for nested in arg.args:
                if isinstance(nested, ast.Constant) and isinstance(nested.value, str):
                    values.append(nested.value)
    return "\n".join(values)


def violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    upgrade = next(
        (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "upgrade"),
        None,
    )
    if upgrade is None:
        return ["missing upgrade()"]

    errors: list[str] = []
    for node in ast.walk(upgrade):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node)
        if name in FORBIDDEN_CALLS:
            errors.append(f"line {node.lineno}: {name} is a contraction; defer it to a later release")
            continue
        if name == "alter_column":
            keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if "new_column_name" in keywords:
                errors.append(f"line {node.lineno}: renaming a column breaks N-1 rollback compatibility")
            if "type_" in keywords:
                errors.append(f"line {node.lineno}: in-place type change is not expand/contract safe")
            nullable = keywords.get("nullable")
            if isinstance(nullable, ast.Constant) and nullable.value is False:
                errors.append(f"line {node.lineno}: nullable=False must be staged after backfill/old-code retirement")
        if name in {"execute", "exec_driver_sql"}:
            sql = constant_sql(node)
            if sql and DESTRUCTIVE_SQL.search(sql):
                errors.append(f"line {node.lineno}: destructive raw SQL in upgrade(): {sql[:80]!r}")
    return errors


def main() -> int:
    try:
        base = base_ref()
        paths = changed_migrations(base)
    except Exception as exc:  # noqa: BLE001
        print(f"rollback_compat_error: cannot establish migration diff base: {exc}", file=sys.stderr)
        return 2

    failed = False
    for path in paths:
        items = violations(path)
        if not items:
            continue
        failed = True
        print(f"❌ {path.relative_to(ROOT)}", file=sys.stderr)
        for item in items:
            print(f"   - {item}", file=sys.stderr)
    if failed:
        print(
            "New Alembic upgrades must be expand/contract compatible with the previous release. "
            "Add new structures first; remove/rename/tighten them only after old code is retired.",
            file=sys.stderr,
        )
        return 1

    print(f"rollback_compat_ok: {len(paths)} changed migration file(s) are N-1 compatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
