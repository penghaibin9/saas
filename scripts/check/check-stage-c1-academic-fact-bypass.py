#!/usr/bin/env python3
"""Stage C1 static gate: formal StudentProfile academic fields have one write command.

This intentionally scans production ``backend/app`` only. It performs lightweight AST
symbol inference for variables loaded from StudentProfile and reports direct writes to
student_status/college_id/major_id/class_id/grade. Creating a new StudentProfile is
allowed; changing an existing profile must go through academic_affairs_student_fact_service.

The old internal major-split implementation is excluded only because the formal router
is bound to academic_affairs_major_split_public_service.confirm; a companion assertion
below fails if that override disappears.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
ACADEMIC_FIELDS = {"student_status", "college_id", "major_id", "class_id", "grade"}
ALLOW_DIRECT_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_student_fact_service.py",
}
NONFORMAL_LEGACY_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_major_split_service.py",
}


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def contains_student_profile(node: ast.AST | None) -> bool:
    return bool(node) and any(isinstance(item, ast.Name) and item.id == "StudentProfile" for item in ast.walk(node))


def infer_loaded_profile_vars(tree: ast.AST) -> set[str]:
    tracked: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            value = node.value
            is_profile_load = contains_student_profile(value) and not (
                isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "StudentProfile"
            )
            is_alias = isinstance(value, ast.Name) and value.id in tracked
            if (is_profile_load or is_alias) and name not in tracked:
                tracked.add(name)
                changed = True
    return tracked


def scan_file(path: pathlib.Path) -> list[str]:
    relative = rel(path)
    if relative in ALLOW_DIRECT_FILES or relative in NONFORMAL_LEGACY_FILES:
        return []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return [f"{relative}: parse error: {exc}"]

    tracked = infer_loaded_profile_vars(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        # s.major_id = ... where s was loaded from StudentProfile.
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in tracked and target.attr in ACADEMIC_FIELDS:
                        violations.append(
                            f"{relative}:{getattr(target, 'lineno', '?')}: direct {target.value.id}.{target.attr} write"
                        )
        # setattr(s, "grade", ...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and node.args[0].id in tracked:
                field = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
                if field in ACADEMIC_FIELDS:
                    violations.append(
                        f"{relative}:{node.lineno}: setattr({node.args[0].id}, {field}) bypass"
                    )
        # query(StudentProfile).update({StudentProfile.grade: ...}) and Core update mappings.
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "StudentProfile" and node.attr in ACADEMIC_FIELDS:
                parent_is_read = False
                # Attribute references are common in SELECT/WHERE. Only flag when the same
                # line contains an update-style mapping key marker, detected from source line.
                line = source.splitlines()[node.lineno - 1] if node.lineno <= len(source.splitlines()) else ""
                if ".update(" in line or "StudentProfile.version" in line:
                    parent_is_read = True
                if parent_is_read and node.attr != "version":
                    violations.append(f"{relative}:{node.lineno}: StudentProfile.{node.attr} update mapping")

    return sorted(set(violations))


def assert_major_split_formal_override() -> list[str]:
    public_path = APP / "modules" / "academic_affairs" / "services" / "academic_affairs_major_split_public_service.py"
    init_path = APP / "modules" / "academic_affairs" / "services" / "__init__.py"
    public = public_path.read_text(encoding="utf-8")
    init = init_path.read_text(encoding="utf-8")
    errors = []
    if "def confirm(user, batch_id)" not in public or "append_student_academic_fact" not in public:
        errors.append("formal major-split confirm is not the Stage C1 AcademicFact override")
    if "academic_affairs_major_split_public_service as academic_affairs_major_split_service" not in init:
        errors.append("services package no longer binds formal major-split to public facade")
    return errors


def main() -> int:
    violations: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        relative = rel(path)
        if "/__pycache__/" in relative:
            continue
        violations.extend(scan_file(path))
    violations.extend(assert_major_split_formal_override())
    if violations:
        print("Stage C1 academic-fact bypass gate FAILED:")
        for item in violations:
            print(f"::error::{item}")
        return 1
    print("Stage C1 academic-fact bypass gate OK: formal direct academic Profile writes = 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
