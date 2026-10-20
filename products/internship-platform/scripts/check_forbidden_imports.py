#!/usr/bin/env python3
"""Fail-close Standalone cross-domain dependency guard."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

FORBIDDEN_PREFIXES = (
    "app.modules.academic_affairs",
    "app.modules.student_affairs",
    "app.modules.graduation",
    "app.modules.orientation",
    "app.modules.campus_service",
    "app.modules.employment",
    "app.modules.platform",
)

# 适配器本身也不得 import 被剥离模块；它们只定义契约/Standalone实现。


def imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [f"<parse-error:{exc}>"]
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def main() -> int:
    violations: list[str] = []
    for path in sorted(BACKEND.rglob("*.py")):
        for module in imports(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(ROOT)} -> {module}")
    if violations:
        print("[standalone-boundary] FORBIDDEN_IMPORTS")
        print("\n".join(violations))
        return 1
    print("[standalone-boundary] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
