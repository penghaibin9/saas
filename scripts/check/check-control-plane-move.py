#!/usr/bin/env python3
"""S0 Move Only structural gate; stdlib-only and fail-closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PAIRS = (
    (
        ROOT / "shared/contracts/control-plane/system-route-snapshot.json",
        ROOT / "backend/app/modules/system_admin/routers/system_bundle.py",
        ROOT / "backend/app/api/v1/system.py",
        "app.modules.system_admin.routers.system_bundle",
    ),
    (
        ROOT / "shared/contracts/control-plane/platform-route-snapshot.json",
        ROOT / "backend/app/modules/platform/routers/platform_bundle.py",
        ROOT / "backend/app/api/v1/platform.py",
        "app.modules.platform.routers.platform_bundle",
    ),
)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    errors: list[str] = []
    for snapshot_path, bundle_path, facade_path, module_name in PAIRS:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        actual = git_blob_sha(bundle_path)
        expected = snapshot["frozenSourceBlobSha"]
        if actual != expected:
            errors.append(f"{bundle_path}: blob drift {actual} != {expected}")
        facade = facade_path.read_text(encoding="utf-8")
        if module_name not in facade:
            errors.append(f"{facade_path}: canonical owner import missing")
        if "router = _bundle.router" not in facade:
            errors.append(f"{facade_path}: facade does not export identical router object")
    locked = ROOT / "backend/app/api/v1/route_registration.py"
    if not locked.exists():
        errors.append("A01-owned route_registration.py unexpectedly missing")
    if errors:
        print("S0 MOVE CONTRACT: RED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("S0 MOVE CONTRACT: GREEN")
    for snapshot_path, bundle_path, _, _ in PAIRS:
        print(f"- {bundle_path.relative_to(ROOT)} == {json.loads(snapshot_path.read_text(encoding='utf-8'))['frozenSourceBlobSha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
