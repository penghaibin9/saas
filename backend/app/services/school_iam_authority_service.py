"""Replayable Control Plane Authority for school IAM permission truth.

This is an explicit provisioning/deployment command surface, not a web-request
fallback and not an application-startup side effect. It materializes the global
Permission Catalog first, then converges immutable SYSTEM RoleTemplate snapshots,
and finally proves zero unexplained B8 shadow drift.
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import system_role_shadow_service as shadow
from app.services.permission_catalog_reconciliation_service import reconcile_permission_catalog


def converge_school_iam_authority(
    *,
    source: str,
    source_commit_sha: str,
    actor_user_id: int | None = None,
) -> dict:
    source_name = str(source or "").strip()
    source_sha = str(source_commit_sha or "").strip()
    if not source_name:
        raise AppException("VALIDATION_ERROR", "school IAM Authority requires source")
    if len(source_sha) < 7:
        raise AppException("VALIDATION_ERROR", "school IAM Authority requires source commit SHA")

    catalog = reconcile_permission_catalog(source=source_name)
    if int(catalog.get("missingAfterReconcile") or 0) != 0:
        raise AppException(
            "PERMISSION_CATALOG_DRIFT",
            "Permission Catalog reconciliation did not converge",
            http_status=409,
            details={"source": source_name},
        )

    templates = shadow.converge_published_system_templates(
        actor_user_id=actor_user_id,
        source_commit_sha=source_sha,
    )
    report = shadow.shadow_system_roles()
    if not report.get("zeroUnexplainedDrift"):
        raise AppException(
            "B8_SYSTEM_SHADOW_DRIFT",
            "SYSTEM RoleTemplate convergence left unexplained drift",
            http_status=409,
            details={
                "unexplainedDriftCount": int(report.get("unexplainedDriftCount") or 0),
                "planeViolationCount": int(report.get("planeViolationCount") or 0),
            },
        )

    return {
        "source": source_name,
        "sourceCommitSha": source_sha,
        "catalogReconciliation": catalog,
        "templateConvergence": templates,
        "shadow": {
            "roleCount": int(report.get("roleCount") or 0),
            "tenantPermissionUniverseCount": int(report.get("tenantPermissionUniverseCount") or 0),
            "unexplainedDriftCount": int(report.get("unexplainedDriftCount") or 0),
            "planeViolationCount": int(report.get("planeViolationCount") or 0),
            "zeroUnexplainedDrift": bool(report.get("zeroUnexplainedDrift")),
        },
        "converged": True,
    }
