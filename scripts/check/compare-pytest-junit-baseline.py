#!/usr/bin/env python3
"""Reject pytest failures that are not present on the PR base branch.

The checked-in baseline is technical-debt metadata, not a blanket xfail list:

* failures and errors are both compared by pytest node id;
* a PR cannot expand its own allowance because the baseline is read from base-ref;
* every changed/new backend test file loses all baseline allowances;
* pytest infrastructure/collection exits other than 0/1 always fail closed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def _normalize_nodeid(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("backend/")


def _nodeid_from_testcase(testcase: ET.Element) -> str:
    name = str(testcase.get("name") or "").strip()
    classname = str(testcase.get("classname") or "").strip()
    if not name:
        raise ValueError("JUnit testcase is missing name")

    # Collection errors are commonly encoded with the source path as testcase.name.
    if ".py" in name and ("/" in name or "\\" in name):
        return _normalize_nodeid(name)

    parts = [part for part in classname.split(".") if part]
    module_index = next(
        (index for index, part in enumerate(parts) if part.startswith("test_")),
        None,
    )
    if module_index is None:
        raise ValueError(f"cannot derive pytest node id from classname={classname!r}, name={name!r}")

    file_path = "/".join(parts[: module_index + 1]) + ".py"
    scopes = parts[module_index + 1 :]
    return "::".join([file_path, *scopes, name])


def failing_nodeids(junit_path: Path) -> set[str]:
    root = ET.parse(junit_path).getroot()
    failures: set[str] = set()
    for testcase in root.iter("testcase"):
        if testcase.find("failure") is None and testcase.find("error") is None:
            continue
        failures.add(_nodeid_from_testcase(testcase))
    return failures


def _read_baseline(path: Path) -> set[str]:
    values: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        values.add(_normalize_nodeid(line))
    return values


def baseline_from_base_ref(repo_root: Path, base_ref: str, baseline_path: Path) -> set[str]:
    repo_relative = baseline_path.resolve().relative_to(repo_root.resolve()).as_posix()
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{repo_relative}"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        values = {
            _normalize_nodeid(line)
            for line in result.stdout.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        return values

    # Bootstrap only: PR #52 introduces the first baseline because main has none yet.
    # Future PRs always use base-ref and therefore cannot grant themselves allowances.
    if not baseline_path.exists():
        raise RuntimeError(
            f"baseline is absent from base ref {base_ref!r} and working tree: {repo_relative}"
        )
    return _read_baseline(baseline_path)


def changed_backend_test_files(repo_root: Path, base_ref: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AMRT", base_ref, "HEAD", "--", "backend/tests"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return {
        _normalize_nodeid(line)
        for line in result.stdout.splitlines()
        if line.strip().endswith(".py")
    }


def compare(
    actual: set[str], baseline: set[str], changed_test_files: set[str]
) -> tuple[set[str], set[str]]:
    protected_baseline = {
        nodeid
        for nodeid in baseline
        if nodeid.split("::", 1)[0] not in changed_test_files
    }
    return actual - protected_baseline, baseline - actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--pytest-exit-code", type=int, required=True)
    args = parser.parse_args()

    if args.pytest_exit_code not in (0, 1):
        print(
            f"pytest infrastructure failed with exit code {args.pytest_exit_code}; refusing baseline comparison",
            file=sys.stderr,
        )
        return 2
    if not args.junit.is_file():
        print(f"JUnit report missing: {args.junit}", file=sys.stderr)
        return 2

    try:
        actual = failing_nodeids(args.junit)
        baseline = baseline_from_base_ref(args.repo_root, args.base_ref, args.baseline)
        changed_tests = changed_backend_test_files(args.repo_root, args.base_ref)
    except (ET.ParseError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"cannot evaluate pytest failure baseline: {exc}", file=sys.stderr)
        return 2

    unexpected, resolved = compare(actual, baseline, changed_tests)
    print(
        "pytest baseline summary: "
        f"actual={len(actual)} known={len(baseline)} changed_test_files={len(changed_tests)} "
        f"unexpected={len(unexpected)} resolved={len(resolved)}"
    )
    if changed_tests:
        print("Changed tests have no baseline allowance:")
        for path in sorted(changed_tests):
            print(f"  {path}")
    if resolved:
        print("Known failures now passing (remove from baseline in a main maintenance change):")
        for nodeid in sorted(resolved):
            print(f"  {nodeid}")
    if unexpected:
        print("Unexpected failures/errors (merge blocked):", file=sys.stderr)
        for nodeid in sorted(unexpected):
            print(f"  {nodeid}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
