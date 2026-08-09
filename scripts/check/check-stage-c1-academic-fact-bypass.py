#!/usr/bin/env python3
"""Stage C1 static gate: formal StudentProfile academic fields have one write command."""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
ACADEMIC_FIELDS = {"student_status", "college_id", "major_id", "class_id", "grade"}
ALLOW_DIRECT_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_student_fact_service.py",
}
NONFORMAL_LEGACY_FILES = {
    "backend/app/modules/academic_affairs/services/academic_affairs_major_split_service.py",
}
PROFILE_HELPER_CALLS = {"_get_profile", "resolve_student", "_student_profile"}


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def contains_student_profile(node: ast.AST | None) -> bool:
    return bool(node) and any(isinstance(item, ast.Name) and item.id == "StudentProfile" for item in ast.walk(node))


def is_known_profile_load(value: ast.AST, tracked: set[str]) -> bool:
    if contains_student_profile(value) and not (
        isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "StudentProfile"
    ):
        return True
    if isinstance(value, ast.Name) and value.id in tracked:
        return True
    if isinstance(value, ast.Call):
        func = value.func
        if isinstance(func, ast.Name) and func.id in PROFILE_HELPER_CALLS:
            return True
        if isinstance(func, ast.Attribute) and func.attr in PROFILE_HELPER_CALLS:
            return True
    return False


def infer_loaded_profile_vars(tree: ast.AST) -> set[str]:
    tracked: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and is_known_profile_load(node.value, tracked) and target.id not in tracked:
                tracked.add(target.id)
                changed = True
    return tracked


def scan_update_calls(tree: ast.AST, relative: str) -> list[str]:
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "update":
            continue
        if not contains_student_profile(node):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Dict):
                continue
            for key in child.keys:
                if isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name):
                    if key.value.id == "StudentProfile" and key.attr in ACADEMIC_FIELDS:
                        violations.append(
                            f"{relative}:{getattr(key, 'lineno', node.lineno)}: StudentProfile.{key.attr} direct update mapping"
                        )
    return violations


def scan_file(path: pathlib.Path) -> list[str]:
    relative = rel(path)
    if relative in ALLOW_DIRECT_FILES or relative in NONFORMAL_LEGACY_FILES:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (UnicodeDecodeError, SyntaxError) as exc:
        return [f"{relative}: parse error: {exc}"]

    tracked = infer_loaded_profile_vars(tree)
    violations = scan_update_calls(tree, relative)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    if target.value.id in tracked and target.attr in ACADEMIC_FIELDS:
                        violations.append(
                            f"{relative}:{getattr(target, 'lineno', '?')}: direct {target.value.id}.{target.attr} write"
                        )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
            if len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and node.args[0].id in tracked:
                field = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
                if field in ACADEMIC_FIELDS:
                    violations.append(f"{relative}:{node.lineno}: setattr({node.args[0].id}, {field}) bypass")
    return sorted(set(violations))


def formal_boundary_assertions() -> list[str]:
    public = (APP / "modules/academic_affairs/services/academic_affairs_major_split_public_service.py").read_text(encoding="utf-8")
    services_init = (APP / "modules/academic_affairs/services/__init__.py").read_text(encoding="utf-8")
    student_service = (APP / "services/student_service.py").read_text(encoding="utf-8")
    errors = []
    if "def confirm(user, batch_id)" not in public or "append_student_academic_fact" not in public:
        errors.append("formal major-split confirm is not the Stage C1 AcademicFact override")
    if "academic_affairs_major_split_public_service as academic_affairs_major_split_service" not in services_init:
        errors.append("services package no longer binds formal major-split to public facade")
    if "db_service.void_student" in student_service:
        errors.append("formal student_service still calls legacy db_service.void_student direct-write")
    return errors


def main() -> int:
    violations = []
    for path in sorted(APP.rglob("*.py")):
        violations.extend(scan_file(path))
    violations.extend(formal_boundary_assertions())
    if violations:
        print("Stage C1 academic-fact bypass gate FAILED:")
        for item in violations:
            print(f"::error::{item}")
        return 1
    print("Stage C1 academic-fact bypass gate OK: formal direct academic Profile writes = 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
