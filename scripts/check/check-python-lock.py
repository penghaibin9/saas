#!/usr/bin/env python3
"""Fail closed when the Python production freeze drifts.

``backend/requirements.in`` is the human-maintained direct dependency policy.
``backend/requirements.lock`` is the exact verified graph.
``backend/requirements.txt`` intentionally mirrors the lock so every existing production/CI
installer remains reproducible without a second installation path.

Exact pins may carry a PEP 508 environment marker when the resolved package itself is platform
conditional (for example uvloop on non-Windows systems). The checker uses only the stdlib so it can
run before dependency installation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "requirements.in"
LOCK = ROOT / "backend" / "requirements.lock"
DEFAULT_INSTALL = ROOT / "backend" / "requirements.txt"
NAME = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?")
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)(?:\s*;\s*(.+))?$")


def norm(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def active_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.split("#", 1)[0].strip()
        if value:
            lines.append(value)
    return lines


def main() -> int:
    for path in (SOURCE, LOCK, DEFAULT_INSTALL):
        if not path.is_file():
            print(f"python_lock_error: missing {path.relative_to(ROOT)}", file=sys.stderr)
            return 2

    direct: set[str] = set()
    for value in active_lines(SOURCE):
        match = NAME.match(value)
        if not match:
            print(f"python_lock_error: cannot parse direct requirement: {value}", file=sys.stderr)
            return 1
        direct.add(norm(match.group(1)))

    locked: dict[str, tuple[str, str]] = {}
    lock_lines = active_lines(LOCK)
    for value in lock_lines:
        match = PIN.fullmatch(value)
        if not match:
            print(
                "python_lock_error: lock entry must be exact name==version with an optional PEP 508 marker: "
                f"{value}",
                file=sys.stderr,
            )
            return 1
        name, version = norm(match.group(1)), match.group(2)
        marker = (match.group(3) or "").strip()
        if name in locked:
            print(f"python_lock_error: duplicate lock entry: {name}", file=sys.stderr)
            return 1
        locked[name] = (version, marker)

    missing = sorted(direct - locked.keys())
    if missing:
        print("python_lock_error: direct dependencies missing from lock:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    if "pytest-timeout" not in locked:
        print("python_lock_error: pytest-timeout must be frozen in requirements.lock", file=sys.stderr)
        return 1

    uvloop = locked.get("uvloop")
    if uvloop is not None:
        marker = uvloop[1].replace("'", '"').replace(" ", "")
        if 'sys_platform!="win32"' not in marker:
            print(
                "python_lock_error: uvloop must be exactly pinned behind sys_platform != \"win32\"; "
                "the repository keeps a supported Windows PowerShell bootstrap",
                file=sys.stderr,
            )
            return 1

    install_lines = active_lines(DEFAULT_INSTALL)
    if install_lines != lock_lines:
        print(
            "python_lock_error: requirements.txt must exactly mirror requirements.lock; "
            "production and CI may otherwise install different graphs",
            file=sys.stderr,
        )
        return 1

    print(
        f"python_lock_ok: {len(direct)} direct deps covered by "
        f"{len(locked)} exact pins; platform markers validated; default installer matches lock"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
