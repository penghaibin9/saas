#!/usr/bin/env python3
"""Fail closed when the Python production lock drifts from requirements.txt.

This checker intentionally uses only the stdlib so it can run before dependency install.
It verifies that every lock entry is an exact ``name==version`` pin, names are unique,
and every direct dependency declared in backend/requirements.txt is represented in the lock.
The installer then runs ``pip check`` to validate the resolved graph itself.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend" / "requirements.txt"
LOCK = ROOT / "backend" / "requirements.lock"
NAME = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?")
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


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
    if not SOURCE.is_file() or not LOCK.is_file():
        print("python_lock_error: requirements.txt/requirements.lock missing", file=sys.stderr)
        return 2

    direct: set[str] = set()
    for value in active_lines(SOURCE):
        match = NAME.match(value)
        if not match:
            print(f"python_lock_error: cannot parse direct requirement: {value}", file=sys.stderr)
            return 1
        direct.add(norm(match.group(1)))

    locked: dict[str, str] = {}
    for value in active_lines(LOCK):
        match = PIN.fullmatch(value)
        if not match:
            print(f"python_lock_error: lock entry is not exact name==version: {value}", file=sys.stderr)
            return 1
        name, version = norm(match.group(1)), match.group(2)
        if name in locked:
            print(f"python_lock_error: duplicate lock entry: {name}", file=sys.stderr)
            return 1
        locked[name] = version

    missing = sorted(direct - locked.keys())
    if missing:
        print("python_lock_error: direct dependencies missing from lock:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    # Canonical tests require pytest-timeout; it belongs in the same reproducible graph rather
    # than being installed as an unbounded second pip command.
    if "pytest-timeout" not in locked:
        print("python_lock_error: pytest-timeout must be frozen in requirements.lock", file=sys.stderr)
        return 1

    print(f"python_lock_ok: {len(direct)} direct deps covered by {len(locked)} exact pins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
