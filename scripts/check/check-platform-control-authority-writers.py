#!/usr/bin/env python3
"""W0 control-plane authority writer/frozen-bundle gate.

Protect two invariants before W1-W7 code-first hardening:
1) platform_bundle.py remains the exact S0 frozen Git blob;
2) production writes to legacy PlatformConfig FEATURES/RULES/WORKFLOWS/BRAND
   remain explicitly inventoried, so a new side writer cannot appear silently.

Only backend/app runtime code is scanned. Tests, scripts, migrations and docs are
not production writers and are intentionally excluded.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
SNAPSHOT = ROOT / "shared" / "contracts" / "control-plane" / "platform-route-snapshot.json"
BASELINE = ROOT / "shared" / "contracts" / "control-plane" / "platform-authority-writers.json"
TARGETS = {"FEATURES", "RULES", "WORKFLOWS", "BRAND"}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def literal_ctype(node: ast.Call) -> str | None:
    if call_name(node) != "put_config_json" or len(node.args) < 2:
        return None
    arg = node.args[1]
    return str(arg.value) if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


def inventory() -> dict[str, list[str]]:
    found = {key: set() for key in sorted(TARGETS)}
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as exc:
            raise SystemExit(f"cannot parse {rel}: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                ctype = literal_ctype(node)
                if ctype in TARGETS:
                    found[ctype].add(rel)
    return {key: sorted(paths) for key, paths in found.items()}


def main() -> int:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    frozen = ROOT / snapshot["canonicalBundlePath"]
    actual_sha = git_blob_sha(frozen)
    expected_sha = str(snapshot["frozenSourceBlobSha"])
    if actual_sha != expected_sha:
        raise SystemExit(
            f"frozen platform bundle changed: expected {expected_sha}, got {actual_sha}"
        )

    actual = inventory()
    expected = {
        key: sorted(value)
        for key, value in baseline["legacyPlatformConfigWriters"].items()
    }
    if actual != expected:
        print(json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False, indent=2))
        raise SystemExit("platform authority writer inventory drifted")

    print(json.dumps({
        "frozenBundleSha": actual_sha,
        "writers": actual,
        "status": "GREEN",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
