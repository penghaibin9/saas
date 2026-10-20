#!/usr/bin/env python3
"""Fail-close local import closure for Standalone W2 staff API."""
from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"


def module_path(module: str) -> Path | None:
    if not module.startswith("app"):
        return None
    parts = module.split(".")[1:]
    base = APP.joinpath(*parts)
    py = base.with_suffix(".py")
    if py.is_file():
        return py
    init = base / "__init__.py"
    if init.is_file():
        return init
    return None


def package_exports(module: str) -> set[str]:
    path = module_path(module)
    if path is None or path.name != "__init__.py":
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                out.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.asname or alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.add(target.id)
    return out


def module_name_for(path: Path) -> str:
    rel = path.relative_to(APP.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def scan(start: str) -> tuple[set[str], list[str]]:
    queue = deque([start])
    seen: set[str] = set()
    missing: set[str] = set()

    while queue:
        module = queue.popleft()
        if module in seen:
            continue
        seen.add(module)
        path = module_path(module)
        if path is None:
            missing.add(module)
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            missing.add(f"{module}::<parse-error:{exc}>")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if not name.startswith("app."):
                        continue
                    if module_path(name) is None:
                        missing.add(name)
                    else:
                        queue.append(name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                base = node.module
                if not base.startswith("app."):
                    continue
                base_path = module_path(base)
                if base_path is None:
                    missing.add(base)
                    continue
                queue.append(base)
                if base_path.name == "__init__.py":
                    exports = package_exports(base)
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        candidate = f"{base}.{alias.name}"
                        if module_path(candidate) is not None:
                            queue.append(candidate)
                        elif (alias.asname or alias.name) not in exports:
                            missing.add(candidate)

    return seen, sorted(missing)


def main() -> int:
    seen, missing = scan("app.api.router")
    print(f"[w2-import-closure] visited={len(seen)} missing={len(missing)}")
    if missing:
        for item in missing:
            print(f"MISSING {item}")
        return 1
    print("[w2-import-closure] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
