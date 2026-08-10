#!/usr/bin/env python3
"""Deterministically split backend pytest files across isolated shards."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


def shard_for(path: str, shard_count: int) -> int:
    digest = hashlib.sha256(path.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-dir", type=Path, default=Path("tests"))
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    args = parser.parse_args()

    if args.shard_count < 1:
        parser.error("--shard-count must be >= 1")
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("--shard-index must be in [0, shard-count)")
    if not args.tests_dir.is_dir():
        print(f"tests directory does not exist: {args.tests_dir}", file=sys.stderr)
        return 2

    files = sorted(
        path.as_posix()
        for path in args.tests_dir.rglob("test_*.py")
        if path.is_file()
    )
    selected = [path for path in files if shard_for(path, args.shard_count) == args.shard_index]
    if not selected:
        print(
            f"shard {args.shard_index}/{args.shard_count} selected no test files",
            file=sys.stderr,
        )
        return 2

    for path in selected:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
