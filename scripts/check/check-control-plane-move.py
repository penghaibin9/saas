#!/usr/bin/env python3
"""S0 Move Only structural gate; allows later adapters without changing frozen bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRS = (
    (ROOT / "shared/contracts/control-plane/system-route-snapshot.json",
     ROOT / "backend/app/modules/system_admin/routers/system_bundle.py",
     ROOT / "backend/app/api/v1/system.py",
     "app.modules.system_admin.routers.system_bundle"),
    (ROOT / "shared/contracts/control-plane/platform-route-snapshot.json",
     ROOT / "backend/app/modules/platform/routers/platform_bundle.py",
     ROOT / "backend/app/api/v1/platform.py",
     "app.modules.platform.routers.platform_bundle"),
)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    errors = []
    for snapshot_path, bundle_path, facade_path, module_name in PAIRS:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        actual = git_blob_sha(bundle_path)
        expected = snapshot["frozenSourceBlobSha"]
        if actual != expected:
            errors.append(f"{bundle_path}: frozen bundle drift {actual} != {expected}")
        facade = facade_path.read_text(encoding="utf-8")
        if module_name not in facade:
            errors.append(f"{facade_path}: canonical frozen bundle import missing")
        if "router = " not in facade:
            errors.append(f"{facade_path}: compatibility router export missing")
    if errors:
        print("S0 MOVE CONTRACT: RED")
        print("\n".join(f"- {e}" for e in errors))
        return 1
    print("S0 MOVE CONTRACT: GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
