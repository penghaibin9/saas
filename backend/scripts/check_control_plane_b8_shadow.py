"""Exact-head B8 SYSTEM shadow production gate."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.modules.platform.services import platform_product_iam_service as product_iam
from app.services import system_role_shadow_service as shadow


def main() -> None:
    head_sha = str(os.environ.get("B8_EXPECTED_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(head_sha) < 7:
        raise RuntimeError("B8_EXPECTED_SHA/GITHUB_SHA is required")
    convergence = shadow.converge_published_system_templates(
        actor_user_id=9901,
        source_commit_sha=head_sha,
    )
    report = shadow.shadow_system_roles()
    if report["unexplainedDriftCount"] != 0:
        raise RuntimeError(f"B8 unexplained SYSTEM drift: {report['mismatches'][:20]}")
    if report["planeViolationCount"] != 0:
        raise RuntimeError(f"B8 template plane violations: {report['planeViolations'][:20]}")
    if not report["zeroUnexplainedDrift"]:
        raise RuntimeError("B8 zeroUnexplainedDrift=false")

    snapshot = product_iam.source_snapshot()
    template_codes = {item["templateCode"] for item in snapshot.get("roleTemplates") or []}
    if any(str(code).startswith("PLATFORM_") for code in template_codes):
        raise RuntimeError("PLATFORM workforce leaked into Product IAM school RoleTemplate snapshot")

    evidence = {
        "schemaVersion": 1,
        "card": "CTRL-B8-01",
        "headSha": head_sha,
        "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "convergence": convergence,
        "shadow": report,
        "productIamTemplateCount": len(snapshot.get("roleTemplates") or []),
        "goldCandidate": True,
    }
    path = Path(os.environ.get("B8_EVIDENCE_PATH") or "../artifacts/control-plane/b8-shadow.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "headSha": head_sha,
        "roleCount": report["roleCount"],
        "tenantPermissionUniverseCount": report["tenantPermissionUniverseCount"],
        "unexplainedDriftCount": report["unexplainedDriftCount"],
        "planeViolationCount": report["planeViolationCount"],
        "createdTemplateVersions": convergence["createdCount"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
