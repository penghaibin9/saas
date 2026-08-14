#!/usr/bin/env python3
"""Machine-readable S0-T inventory for academic-affairs pytest assets.

The construction master requires the P0 refactor to select tests from a repeatable
inventory rather than model memory.  This script scans the four authoritative test
patterns, extracts static pytest nodeids, classifies each node, records whether it is
still present in the known-failure ledger, and derives production owners from imports.

It is intentionally stdlib-only so it can run in CI before application imports.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = REPO_ROOT / "backend" / "tests"
LEDGER_PATH = REPO_ROOT / "scripts" / "check" / "backend-known-failures-main.txt"

TEST_GLOBS = (
    "test_aa_*.py",
    "*academic*.py",
    "*graduation*.py",
    "*selection*.py",
)

DOMAIN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("D1_TERM_CALENDAR", ("term", "calendar", "time_slot", "timeslot", "time-band", "time_band")),
    ("D2_ROSTER_REGISTRATION", ("roster", "registration", "student_academic_fact")),
    ("D3_STATUS_CHANGE", ("status_change", "status-change", "temporal", "future_effective", "future-effective")),
    ("D4_PROGRAM_COURSE_TASK", ("program", "course", "teaching_task", "teaching-task", "teaching_class", "teaching-class")),
    ("D5_SCHEDULE_RESOURCE", ("schedule", "scheduling", "autoschedule", "resource", "classroom")),
    ("D6_SELECTION", ("selection", "eligibility", "teaching_roster", "teaching-roster")),
    ("D7_EXAM_MAKEUP", ("exam", "makeup", "clearance", "invigil")),
    ("D8_GRADE", ("grade", "transcript", "recheck", "score")),
    ("D9_FINAL_DOMAINS", ("graduation", "evaluation", "textbook", "warning", "archive", "stats")),
)

COMPAT_HINTS = (
    "compat",
    "legacy",
    "facade",
    "entrypoint",
    "import_boundary",
    "barrel",
    "public_service",
    "final_service",
)
WHITEBOX_HINTS = (
    "registry",
    "bundle",
    "metadata",
    "schema_contract",
    "route_registration",
    "install_order",
    "module_identity",
    "__module__",
    "inspect.",
    "importlib.",
)
BLACKBOX_HINTS = (
    "testclient",
    "asyncclient",
    "client.get(",
    "client.post(",
    "client.put(",
    "client.delete(",
    "client.patch(",
)


def _candidate_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in TEST_GLOBS:
        files.update(path for path in TEST_ROOT.glob(pattern) if path.is_file())
    return sorted(files)


def _ledger_nodeids() -> set[str]:
    if not LEDGER_PATH.exists():
        return set()
    nodeids: set[str] = set()
    for raw in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            nodeids.add(line)
    return nodeids


def _iter_test_nodes(tree: ast.Module) -> Iterable[tuple[str, ast.AST]]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node.name, node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    yield f"{node.name}::{child.name}", child


def _domain_for(file_path: str, nodeid: str) -> str:
    haystack = f"{file_path}::{nodeid}".lower().replace("-", "_")
    for domain, hints in DOMAIN_RULES:
        if any(hint.replace("-", "_") in haystack for hint in hints):
            return domain
    return "CROSS_DOMAIN"


def _kind_for(source: str, file_path: str, nodeid: str, in_ledger: bool) -> str:
    if in_ledger:
        return "CI_DEBT"
    haystack = f"{file_path}\n{nodeid}\n{source}".lower()
    if any(hint in haystack for hint in COMPAT_HINTS):
        return "COMPAT"
    if any(hint in haystack for hint in BLACKBOX_HINTS):
        return "BLACKBOX"
    if any(hint in haystack for hint in WHITEBOX_HINTS):
        return "WHITEBOX"
    # Tests without HTTP-client calls are conservatively treated as white-box assets;
    # this keeps the four requested categories exhaustive without inventing a fifth class.
    return "WHITEBOX"


def _production_owners(tree: ast.Module) -> list[str]:
    owners: set[str] = set()
    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.ImportFrom):
            module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app.modules.academic_affairs") or alias.name.startswith("app.models.academic_affairs"):
                    owners.add(alias.name)
        if module and (
            module.startswith("app.modules.academic_affairs")
            or module.startswith("app.models.academic_affairs")
        ):
            owners.add(module)
    return sorted(owners) or ["app.modules.academic_affairs"]


def build_inventory() -> dict:
    ledger = _ledger_nodeids()
    rows: list[dict] = []
    matched_by_glob = {
        pattern: len([path for path in TEST_ROOT.glob(pattern) if path.is_file()])
        for pattern in TEST_GLOBS
    }

    for path in _candidate_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        owners = _production_owners(tree)
        for suffix, node in _iter_test_nodes(tree):
            nodeid = f"{relative}::{suffix}"
            in_ledger = nodeid in ledger
            node_source = ast.get_source_segment(source, node) or ""
            rows.append(
                {
                    "test_file": relative,
                    "nodeid": nodeid,
                    "business_domain": _domain_for(relative, nodeid),
                    "test_kind": _kind_for(node_source, relative, nodeid, in_ledger),
                    "in_known_failure_ledger": in_ledger,
                    "production_owner": owners,
                }
            )

    rows.sort(key=lambda row: row["nodeid"])
    return {
        "inventory_version": 1,
        "scan_patterns": list(TEST_GLOBS),
        "matched_files_by_pattern": matched_by_glob,
        "known_failure_ledger": LEDGER_PATH.relative_to(REPO_ROOT).as_posix(),
        "known_failure_count": len(ledger),
        "test_file_count": len({row["test_file"] for row in rows}),
        "nodeid_count": len(rows),
        "tests": rows,
    }


def validate_inventory(inventory: dict) -> list[str]:
    errors: list[str] = []
    tests = inventory.get("tests") or []
    if not tests:
        errors.append("academic-affairs test inventory is empty")

    nodeids = [row.get("nodeid") for row in tests]
    duplicates = sorted({nodeid for nodeid in nodeids if nodeids.count(nodeid) > 1})
    if duplicates:
        errors.append(f"duplicate nodeids: {duplicates[:10]}")

    required = {
        "test_file",
        "nodeid",
        "business_domain",
        "test_kind",
        "in_known_failure_ledger",
        "production_owner",
    }
    for index, row in enumerate(tests):
        missing = required - set(row)
        if missing:
            errors.append(f"row {index} missing fields: {sorted(missing)}")
        if row.get("test_kind") not in {"BLACKBOX", "WHITEBOX", "COMPAT", "CI_DEBT"}:
            errors.append(f"row {index} invalid test_kind: {row.get('test_kind')}")
        if not row.get("production_owner"):
            errors.append(f"row {index} has no production_owner")

    for pattern, count in inventory.get("matched_files_by_pattern", {}).items():
        if count == 0:
            errors.append(f"authoritative scan pattern matched no files: {pattern}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate inventory and fail closed")
    parser.add_argument("--output", type=Path, help="write JSON to a file instead of stdout")
    args = parser.parse_args()

    inventory = build_inventory()
    errors = validate_inventory(inventory) if args.check else []
    payload = dict(inventory)
    if args.check:
        payload["validation_errors"] = errors

    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
