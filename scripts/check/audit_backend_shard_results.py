#!/usr/bin/env python3
"""Merge four pytest shard reports and compare them with the main failure ledger."""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import copy
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def normalize_nodeid(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("backend/")


def nodeid_from_testcase(testcase: ET.Element) -> str:
    name = str(testcase.get("name") or "").strip()
    classname = str(testcase.get("classname") or "").strip()
    if not name:
        raise ValueError("JUnit testcase is missing name")
    if ".py" in name and ("/" in name or "\\" in name):
        return normalize_nodeid(name)

    parts = [part for part in classname.split(".") if part]
    module_index = next(
        (index for index, part in enumerate(parts) if part.startswith("test_")),
        None,
    )
    if module_index is None:
        raise ValueError(
            f"cannot derive pytest node id from classname={classname!r}, name={name!r}"
        )
    file_path = "/".join(parts[: module_index + 1]) + ".py"
    scopes = parts[module_index + 1 :]
    return normalize_nodeid("::".join([file_path, *scopes, name]))


def read_baseline(path: Path) -> set[str]:
    return {
        normalize_nodeid(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def parse_junits(paths: list[Path]) -> tuple[set[str], set[str]]:
    failures: set[str] = set()
    errors: set[str] = set()
    for path in paths:
        root = ET.parse(path).getroot()
        for testcase in root.iter("testcase"):
            nodeid = nodeid_from_testcase(testcase)
            if testcase.find("error") is not None:
                errors.add(nodeid)
            elif testcase.find("failure") is not None:
                failures.add(nodeid)
    return failures, errors


def merge_junits(paths: list[Path], output: Path) -> None:
    merged = ET.Element("testsuites")
    for path in paths:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        for suite in suites:
            merged.append(copy.deepcopy(suite))
    ET.ElementTree(merged).write(output, encoding="utf-8", xml_declaration=True)


def _static_test_signatures(path: Path) -> set[str] | None:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return None

    signatures: set[str] = set()

    def walk(nodes: list[ast.stmt], prefix: list[str]) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    signatures.add("::".join([*prefix, node.name]))
            elif isinstance(node, ast.ClassDef):
                walk(node.body, [*prefix, node.name])

    walk(module.body, [])
    return signatures


def baseline_entry_exists(nodeid: str, backend_root: Path) -> bool:
    parts = normalize_nodeid(nodeid).split("::")
    file_path = backend_root / parts[0]
    if not file_path.is_file():
        return False
    if len(parts) == 1:
        return True

    signatures = _static_test_signatures(file_path)
    if signatures is None:
        # Fail closed against false stale classification when source parsing is uncertain.
        return True
    requested = list(parts[1:])
    requested[-1] = re.sub(r"\[.*\]$", "", requested[-1])
    return "::".join(requested) in signatures


def write_list(path: Path, values: set[str]) -> None:
    text = "".join(f"{value}\n" for value in sorted(values))
    path.write_text(text, encoding="utf-8")


def verify_shard_manifests(
    manifests: list[Path], backend_root: Path, expected_shards: int
) -> tuple[dict[str, int], list[str]]:
    problems: list[str] = []
    if len(manifests) != expected_shards:
        problems.append(
            f"expected {expected_shards} shard target manifests, found {len(manifests)}"
        )

    owners: dict[str, list[str]] = defaultdict(list)
    counts: dict[str, int] = {}
    for manifest in manifests:
        entries = [
            line.strip().replace("\\", "/")
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        counts[manifest.name] = len(entries)
        for entry in entries:
            owners[entry].append(manifest.name)

    duplicates = {path: names for path, names in owners.items() if len(names) != 1}
    if duplicates:
        problems.append(f"{len(duplicates)} test files appear in multiple shard manifests")

    expected = {
        path.relative_to(backend_root).as_posix()
        for path in (backend_root / "tests").rglob("test_*.py")
        if path.is_file()
    }
    actual = set(owners)
    missing = expected - actual
    extra = actual - expected
    if missing:
        problems.append(f"{len(missing)} backend test files are missing from shard manifests")
    if extra:
        problems.append(f"{len(extra)} shard targets do not exist in backend/tests")
    return counts, problems


def read_exit_statuses(status_files: list[Path], expected_shards: int) -> tuple[dict[str, int], list[str]]:
    problems: list[str] = []
    statuses: dict[str, int] = {}
    if len(status_files) != expected_shards:
        problems.append(
            f"expected {expected_shards} pytest status files, found {len(status_files)}"
        )
    for path in status_files:
        try:
            value = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            problems.append(f"invalid pytest status file: {path.name}")
            continue
        statuses[path.name] = value
        if value not in (0, 1):
            problems.append(f"{path.name} has infrastructure pytest exit code {value}")
    return statuses, problems


def section(title: str, values: set[str]) -> str:
    lines = [f"## {title} ({len(values)})", ""]
    if not values:
        lines.append("- none")
    else:
        lines.extend(f"- `{value}`" for value in sorted(values))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--backend-root", type=Path, default=Path("backend"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-shards", type=int, default=4)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    junit_paths = sorted(args.artifact_dir.rglob("backend-shard-*.xml"))
    manifests = sorted(args.artifact_dir.rglob("shard-targets-*.txt"))
    status_files = sorted(args.artifact_dir.rglob("pytest-exit-*.txt"))

    infrastructure_problems: list[str] = []
    if len(junit_paths) != args.expected_shards:
        infrastructure_problems.append(
            f"expected {args.expected_shards} JUnit reports, found {len(junit_paths)}"
        )

    shard_counts, manifest_problems = verify_shard_manifests(
        manifests, args.backend_root, args.expected_shards
    )
    statuses, status_problems = read_exit_statuses(status_files, args.expected_shards)
    infrastructure_problems.extend(manifest_problems)
    infrastructure_problems.extend(status_problems)

    try:
        baseline = read_baseline(args.baseline)
        failures, errors = parse_junits(junit_paths)
        if junit_paths:
            merge_junits(junit_paths, args.output_dir / "backend-all-shards.xml")
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"cannot audit backend shard results: {exc}", file=sys.stderr)
        return 2

    actual = failures | errors
    stale = {nodeid for nodeid in baseline if not baseline_entry_exists(nodeid, args.backend_root)}
    still_failing = actual & baseline
    natural_recovered = baseline - actual - stale
    new_failures = actual - baseline

    write_list(args.output_dir / "current-failures.txt", failures)
    write_list(args.output_dir / "current-errors.txt", errors)
    write_list(args.output_dir / "still-failing.txt", still_failing)
    write_list(args.output_dir / "natural-recovered.txt", natural_recovered)
    write_list(args.output_dir / "new-failures.txt", new_failures)
    write_list(args.output_dir / "stale-baseline.txt", stale)

    summary = [
        "# Backend pytest 4-shard baseline audit",
        "",
        f"- Baseline ledger: **{len(baseline)}** nodeids",
        f"- Current failures: **{len(failures)}**",
        f"- Current errors: **{len(errors)}**",
        f"- Current failed/error union: **{len(actual)}**",
        f"- Still failing from baseline: **{len(still_failing)}**",
        f"- Naturally recovered: **{len(natural_recovered)}**",
        f"- New failures/errors: **{len(new_failures)}**",
        f"- Stale baseline entries: **{len(stale)}**",
        "",
        "## Shard manifests",
        "",
    ]
    for name, count in sorted(shard_counts.items()):
        summary.append(f"- `{name}`: {count} test files")
    summary.extend(["", "## Pytest exit statuses", ""])
    for name, value in sorted(statuses.items()):
        summary.append(f"- `{name}`: {value}")

    if infrastructure_problems:
        summary.extend(["", "## Infrastructure problems", ""])
        summary.extend(f"- {problem}" for problem in infrastructure_problems)
        summary.append("")

    summary_text = "\n".join(summary) + "\n\n"
    summary_text += section("Still failing", still_failing)
    summary_text += section("Naturally recovered", natural_recovered)
    summary_text += section("New failures/errors", new_failures)
    summary_text += section("Stale baseline entries", stale)
    report_path = args.output_dir / "backend-baseline-audit.md"
    report_path.write_text(summary_text, encoding="utf-8")
    print("\n".join(summary[:8]))

    if infrastructure_problems:
        return 2
    if new_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
