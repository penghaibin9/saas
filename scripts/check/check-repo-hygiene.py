from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "scripts" / "check" / "repo-hygiene-allowlist.json"


def tracked_files() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return sorted(item.decode("utf-8") for item in raw.split(b"\0") if item)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def is_forbidden(relative: str) -> bool:
    parts = relative.split("/")
    if relative.startswith(("tmp/", "_run/", ".codex-artifacts/", ".codex-temp/")):
        return True
    if relative.startswith("artifacts/") and not relative.startswith("artifacts/release-seals/"):
        return True
    if any(part in {"node_modules", "dist", "__pycache__", ".pytest_cache", "test-results"} for part in parts):
        return True
    return relative.endswith((".log", ".pyc", ".pyo", ".junit.xml"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="artifacts/release-seals/repo-hygiene.json")
    parser.add_argument("--fail-on-duplicates", action="store_true")
    args = parser.parse_args()
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    large_allow = set(policy["largeFileAllowlist"])
    duplicate_prefixes = tuple(policy["duplicateAllowedPrefixes"])
    duplicate_groups = {
        frozenset(entry["paths"]): entry["reason"]
        for entry in policy.get("duplicateAllowedGroups", [])
    }

    forbidden: list[str] = []
    oversized: list[dict[str, object]] = []
    by_hash: dict[str, list[str]] = defaultdict(list)
    for relative in tracked_files():
        path = ROOT / relative
        if not path.is_file():
            continue
        if is_forbidden(relative):
            forbidden.append(relative)
        size = path.stat().st_size
        if size > policy["maxTrackedFileBytes"] and relative not in large_allow:
            oversized.append({"path": relative, "sizeBytes": size})
        if size > 0:
            by_hash[digest(path)].append(relative)

    duplicates = []
    for sha, paths in sorted(by_hash.items()):
        if len(paths) < 2:
            continue
        if all(path.startswith(duplicate_prefixes) for path in paths):
            continue
        if frozenset(paths) in duplicate_groups:
            continue
        duplicates.append({"sha256": sha, "paths": paths})

    report = {
        "schemaVersion": 1,
        "forbiddenTracked": forbidden,
        "oversizedTracked": oversized,
        "duplicateGroups": duplicates,
        "passed": not forbidden and not oversized and (not args.fail_on_duplicates or not duplicates),
    }
    output = ROOT / args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"forbidden={len(forbidden)} oversized={len(oversized)} duplicates={len(duplicates)} "
        f"report={output.relative_to(ROOT)}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
