#!/usr/bin/env python3
"""Validate newly changed production file capabilities.

The frozen inventory describes runtime capabilities. Tests, CI helpers and audit scripts may mention
UploadFile/FileResponse/ZIP as evidence tooling; they are not user-facing capabilities and must not
pollute the runtime registry. They remain covered by their own CI/tests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import audit_file_capabilities as audit


def _production_changed_paths(base_ref: str) -> list[Path]:
    allowed_prefixes = tuple(f"{name.rstrip('/')}/" for name in audit.SCAN_ROOTS)
    paths: list[Path] = []
    for relative in audit.git_changed_files(base_ref):
        normalized = relative.replace("\\", "/")
        if not normalized.startswith(allowed_prefixes):
            continue
        path = audit.ROOT / normalized
        if path.is_file() and path.suffix.lower() in audit.SOURCE_SUFFIXES:
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=audit.DEFAULT_INVENTORY)
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args()

    entries = audit.inventory_entries(args.inventory)
    candidates = audit.discover(_production_changed_paths(args.base_ref))
    uncovered = [item for item in candidates if not audit.is_covered(item, entries)]
    if uncovered:
        print("changed production file capabilities must be registered:", file=sys.stderr)
        for item in uncovered:
            print(
                f"- {item.source}:{item.line} [{item.capability}] {item.token}",
                file=sys.stderr,
            )
        return 1
    print("all changed production file capabilities registered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
