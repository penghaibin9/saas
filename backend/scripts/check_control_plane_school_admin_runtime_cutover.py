"""Exact-head runtime proof for SCHOOL_ADMIN wildcard retirement."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.permissions import ROLE_PERMISSIONS, get_base_permission_patterns
from app.core.school_admin_permission_resolver import catalog_school_admin_permissions
from app.services import system_role_shadow_service as shadow


def main() -> None:
    head_sha = str(os.environ.get("SCHOOL_ADMIN_CUTOVER_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("SCHOOL_ADMIN_CUTOVER_EXPECTED_SHA/GITHUB_SHA is required")

    legacy = set(ROLE_PERMISSIONS.get("SCHOOL_ADMIN") or ())
    if legacy != {"*"}:
        raise RuntimeError(f"legacy B8 SCHOOL_ADMIN shadow baseline drifted: {sorted(legacy)}")

    convergence = shadow.converge_published_system_templates(
        actor_user_id=9921,
        source_commit_sha=head_sha,
    )
    report = shadow.shadow_system_roles()
    if not report.get("zeroUnexplainedDrift"):
        raise RuntimeError(f"SYSTEM shadow drift blocks wildcard retirement: {report}")

    expected = set(catalog_school_admin_permissions())
    user = {
        "userId": "db-9921",
        "tenantId": "1",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "STAFF",
    }
    runtime = set(get_base_permission_patterns(user))
    if runtime != expected:
        missing = sorted(expected - runtime)
        extra = sorted(runtime - expected)
        raise RuntimeError(
            "SCHOOL_ADMIN runtime explicit snapshot drift "
            f"expected={len(expected)} actual={len(runtime)} missing={missing[:20]} extra={extra[:20]}"
        )
    if "*" in runtime:
        raise RuntimeError("SCHOOL_ADMIN runtime still consumes wildcard")
    if any(code.startswith("platform.") or code.startswith("enterprise.") for code in runtime):
        raise RuntimeError("SCHOOL_ADMIN runtime crossed permission plane")

    evidence = {
        "schemaVersion": 1,
        "card": "CTRL-B8-WILDCARD-RETIREMENT-RUNTIME",
        "headSha": head_sha,
        "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "legacySchoolAdminWildcardShadowStillPresent": True,
        "legacyWildcardRuntimeReachable": False,
        "runtimeSchoolAdminWildcardStillPresent": False,
        "runtimeSchoolAdminWildcardRetired": True,
        "runtimeResolver": "PUBLISHED_TENANT_ROLE_TEMPLATE",
        "runtimePermissionCount": len(runtime),
        "tenantPermissionUniverseCount": len(expected),
        "runtimeExactSnapshot": runtime == expected,
        "platformPermissionCount": sum(1 for code in runtime if code.startswith("platform.")),
        "enterprisePermissionCount": sum(1 for code in runtime if code.startswith("enterprise.")),
        "dbFailurePolicy": "FAIL_CLOSED",
        "shadow": {
            "roleCount": report["roleCount"],
            "unexplainedDriftCount": report["unexplainedDriftCount"],
            "planeViolationCount": report["planeViolationCount"],
            "zeroUnexplainedDrift": report["zeroUnexplainedDrift"],
        },
        "templateConvergence": convergence,
        "cutoverComplete": True,
    }
    target = Path(
        os.environ.get("SCHOOL_ADMIN_CUTOVER_EVIDENCE_PATH")
        or "../artifacts/control-plane/school-admin-runtime-cutover.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
