"""Exact-head SCHOOL_ADMIN wildcard-retirement snapshot preflight."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.permissions import ROLE_PERMISSIONS
from app.core.school_admin_permission_resolver import school_admin_cutover_preflight
from app.services import system_role_shadow_service as shadow


def main() -> None:
    head_sha = str(os.environ.get("SCHOOL_ADMIN_RETIREMENT_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("SCHOOL_ADMIN_RETIREMENT_EXPECTED_SHA/GITHUB_SHA is required")

    # The static wildcard is retained only as the OLD resolver side of B8 shadow.
    # This preflight never claims whether runtime currently consumes that token.
    if set(ROLE_PERMISSIONS.get("SCHOOL_ADMIN") or ()) != {"*"}:
        raise RuntimeError("preflight requires the legacy SCHOOL_ADMIN shadow baseline to remain frozen")

    convergence = shadow.converge_published_system_templates(
        actor_user_id=9911,
        source_commit_sha=head_sha,
    )
    report = shadow.shadow_system_roles()
    if not report.get("zeroUnexplainedDrift"):
        raise RuntimeError(f"SYSTEM shadow drift blocks wildcard retirement: {report}")

    proof = school_admin_cutover_preflight()
    if not proof.get("exactSnapshot"):
        raise RuntimeError(f"SCHOOL_ADMIN explicit snapshot not exact: {proof}")
    if proof.get("explicitPermissionCount") != proof.get("tenantPermissionUniverseCount"):
        raise RuntimeError(f"SCHOOL_ADMIN permission count drift: {proof}")
    if int(proof.get("explicitPermissionCount") or 0) <= 400:
        raise RuntimeError(f"SCHOOL_ADMIN permission universe unexpectedly small: {proof}")
    if proof.get("containsRuntimeWildcard"):
        raise RuntimeError("published SCHOOL_ADMIN template must be concrete-only")
    if proof.get("platformPermissionCount") or proof.get("enterprisePermissionCount"):
        raise RuntimeError(f"forbidden permission plane entered SCHOOL_ADMIN template: {proof}")

    evidence = {
        "schemaVersion": 2,
        "card": "CTRL-B8-WILDCARD-RETIREMENT-PREFLIGHT",
        "headSha": head_sha,
        "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "legacySchoolAdminWildcardShadowBaselinePresent": True,
        "runtimeCutoverState": "NOT_EVALUATED_BY_PREFLIGHT",
        "preflight": proof,
        "shadow": {
            "roleCount": report["roleCount"],
            "tenantPermissionUniverseCount": report["tenantPermissionUniverseCount"],
            "unexplainedDriftCount": report["unexplainedDriftCount"],
            "planeViolationCount": report["planeViolationCount"],
            "zeroUnexplainedDrift": report["zeroUnexplainedDrift"],
        },
        "templateConvergence": convergence,
        "snapshotReady": True,
    }
    target = Path(
        os.environ.get("SCHOOL_ADMIN_RETIREMENT_EVIDENCE_PATH")
        or "../artifacts/control-plane/school-admin-retirement-preflight.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
