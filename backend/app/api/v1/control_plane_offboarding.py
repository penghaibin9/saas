"""Platform-only tenant offboarding/destruction API."""
from __future__ import annotations

import os
import time
from fastapi import APIRouter, Body, Depends

from app.core.exceptions import AppException
from app.core.response import success
from app.modules.platform.routers.platform_bundle import require_platform_super_admin
from app.services import audit_log
from app.services import tenant_offboarding_service as offboarding

router = APIRouter(prefix="/platform", tags=["16·平台总控（租户退租销毁）"])


def _require_destructive_assurance(user: dict) -> None:
    """Use server-verified JWT assurance claims exposed by app.core.security."""
    raw_time = user.get("authTime") or user.get("tokenIat")
    try:
        age = int(time.time()) - int(raw_time)
    except (TypeError, ValueError):
        age = 10**9
    amr = {str(item).lower() for item in (user.get("amr") or [])}
    acr = str(user.get("acr") or "").lower()
    if age < 0 or age > 600 or ("mfa" not in amr and "mfa" not in acr):
        raise AppException(
            "STEP_UP_REQUIRED",
            "租户物理销毁需要10分钟内完成的平台多因素重新认证",
            http_status=403,
            details={"maxAuthAgeSeconds": 600, "mfaRequired": True},
        )


def _with_version(job: dict | None) -> dict | None:
    if job is None:
        return None
    from app.services.tenant_effective_state_service import get_effective_state
    try:
        state = get_effective_state(int(job["tenantId"]), strict=True)
        return {**job, "tenantVersion": int(state["version"]), "effectiveState": state}
    except Exception:
        return {**job, "tenantVersion": None}


@router.get("/tenants/{tenant_id}/offboarding/preview", summary="退租影响预演（只读）")
def preview(tenant_id: int, user=Depends(require_platform_super_admin)):
    return success(offboarding.preview_offboarding(tenant_id))


@router.post("/tenants/{tenant_id}/offboarding/request", summary="发起退租并立即冻结业务写入")
def request_offboarding(tenant_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    expected = body.get("expectedVersion")
    if expected is None:
        raise AppException("VALIDATION_ERROR", "发起退租必须提供 expectedVersion")
    out = offboarding.request_offboarding(
        user, tenant_id,
        reason=body.get("reason") or "",
        expected_version=int(expected),
        retention_days=int(body.get("retentionDays") if body.get("retentionDays") is not None else 30),
    )
    audit_log.record("PLATFORM_TENANT_OFFBOARDING_REQUEST", str(tenant_id),
                     detail={"jobId": out["jobId"], "reason": body.get("reason")},
                     result="SUCCESS", tenant_id=tenant_id)
    return success(_with_version(out), message="退租任务已创建，租户已冻结为只读")


@router.get("/tenants/{tenant_id}/offboarding", summary="租户最近退租任务")
def tenant_offboarding(tenant_id: int, user=Depends(require_platform_super_admin)):
    return success(_with_version(offboarding.get_active_job_for_tenant(tenant_id)))


@router.get("/tenant-offboarding/{job_id}", summary="退租任务详情")
def job_get(job_id: int, user=Depends(require_platform_super_admin)):
    return success(_with_version(offboarding.get_job(job_id)))


@router.post("/tenant-offboarding/{job_id}/final-export", summary="确认最终数据导出摘要并进入保留期")
def confirm_export(job_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = offboarding.confirm_final_export(user, job_id, sha256=body.get("finalExportSha256") or "")
    audit_log.record("PLATFORM_TENANT_OFFBOARDING_FINAL_EXPORT", out["tenantId"],
                     detail={"jobId": out["jobId"], "finalExportSha256": out["finalExportSha256"]},
                     result="SUCCESS", tenant_id=int(out["tenantId"]))
    return success(_with_version(out), message="最终导出已确认，租户已进入保留期")


@router.post("/tenant-offboarding/{job_id}/cancel", summary="在不可逆边界前取消退租")
def cancel(job_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    out = offboarding.cancel_offboarding(user, job_id, reason=body.get("reason") or "")
    audit_log.record("PLATFORM_TENANT_OFFBOARDING_CANCEL", out["tenantId"],
                     detail={"jobId": out["jobId"], "reason": body.get("reason")},
                     result="SUCCESS", tenant_id=int(out["tenantId"]))
    return success(_with_version(out), message="退租任务已取消")


@router.post("/tenant-offboarding/{job_id}/approve-purge", summary="批准并执行不可逆租户物理销毁")
def approve_purge(job_id: int, body: dict = Body(...), user=Depends(require_platform_super_admin)):
    _require_destructive_assurance(user)
    expected = body.get("expectedVersion")
    if expected is None:
        raise AppException("VALIDATION_ERROR", "物理销毁必须提供 expectedVersion")
    confirm = str(body.get("confirmText") or "").strip()
    if confirm != "永久销毁租户数据":
        raise AppException("VALIDATION_ERROR", "请精确输入“永久销毁租户数据”确认不可逆操作")
    source_commit = os.getenv("APP_COMMIT_SHA") or os.getenv("GITHUB_SHA") or "unknown"
    out = offboarding.approve_and_purge(
        user, job_id, expected_version=int(expected), source_commit=source_commit,
    )
    audit_log.record("PLATFORM_TENANT_PURGE_COMPLETED", out["tenantId"],
                     detail={"jobId": out["jobId"], "purgeEvidenceSha256": out["purgeEvidenceSha256"]},
                     result="SUCCESS", tenant_id=int(out["tenantId"]))
    return success(out, message="租户数据物理销毁完成，已生成销毁证据")
