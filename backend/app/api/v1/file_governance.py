"""学校自助文件存储治理 API；只返回统计和异常，不授予文件内容查看权。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.services import file_storage_governance_service as governance

router = APIRouter(prefix="/governance", tags=["文件中心·存储治理"])


class QuotaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    totalQuotaBytes: int = Field(..., gt=0)
    warningPercent: int = Field(80, ge=1, le=100)
    hardLimitEnabled: bool = True
    moduleQuotaBytes: dict[str, int] = Field(default_factory=dict)
    description: str | None = Field(None, max_length=500)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policyCode: str = Field(..., min_length=2, max_length=100)
    moduleCode: str | None = Field(None, max_length=64)
    bizType: str | None = Field(None, max_length=80)
    storageZone: str | None = Field(None, max_length=30)
    retentionDays: int = Field(..., ge=0, le=36500)
    cleanupAction: str = Field("DELETE_BYTES", max_length=30)
    priority: int = Field(100, ge=0, le=10000)
    active: bool = True
    description: str | None = Field(None, max_length=500)


class CleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dryRun: bool = True
    limit: int = Field(500, ge=1, le=5000)


class LegalHoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    reason: str = Field(..., min_length=5, max_length=500)


@router.get("/overview", summary="租户容量、增长、分区、模块和异常概览")
def overview(user=Depends(require_permission("systemAdmin.file.manage"))):
    return success(governance.governance_overview())


@router.put("/quota", summary="配置租户总配额和模块配额")
def set_quota(body: QuotaRequest, user=Depends(require_permission("systemAdmin.file.manage"))):
    return success(governance.upsert_quota(
        total_quota_bytes=body.totalQuotaBytes,
        warning_percent=body.warningPercent,
        hard_limit_enabled=body.hardLimitEnabled,
        module_quota_json={str(k).upper(): int(v) for k, v in body.moduleQuotaBytes.items()},
        description=body.description,
        user=user,
    ), message="存储配额已更新")


@router.get("/retention-policies", summary="列出租户保留策略")
def retention_policies(user=Depends(require_permission("systemAdmin.file.manage"))):
    return success({"items": governance.list_policies()})


@router.post("/retention-policies", summary="新增或更新保留策略")
def save_retention_policy(body: PolicyRequest, user=Depends(require_permission("systemAdmin.file.manage"))):
    return success(governance.upsert_policy(body.model_dump(), user=user), message="保留策略已保存")


@router.post("/retention/backfill", summary="为历史空值文件补算保留截止")
def backfill_retention(
    limit: int = Query(500, ge=1, le=5000),
    user=Depends(require_permission("systemAdmin.file.manage")),
):
    from app.core.context import current_tenant_id

    return success(governance.backfill_retention(tenant_id=int(current_tenant_id()), limit=limit))


@router.post("/cleanup", summary="预演或执行到期清理")
def cleanup(body: CleanupRequest, user=Depends(require_permission("systemAdmin.file.manage"))):
    from app.core.context import current_tenant_id

    return success(governance.cleanup_expired(
        tenant_id=int(current_tenant_id()),
        dry_run=body.dryRun,
        limit=body.limit,
    ), message="清理预演完成" if body.dryRun else "到期清理完成")


@router.post("/files/{file_id}/legal-hold", summary="设置或解除法律保留")
def legal_hold(
    file_id: str,
    body: LegalHoldRequest,
    user=Depends(require_permission("systemAdmin.file.manage")),
):
    return success(governance.set_legal_hold(
        file_id,
        enabled=body.enabled,
        reason=body.reason,
        user=user,
    ), message="法律保留状态已更新")
