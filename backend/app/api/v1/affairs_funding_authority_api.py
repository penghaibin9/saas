"""包 10：资助批准金额双人复核补充 API + 发放台账安全导出。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field, condecimal

from app.api.v1.file_contract import validated_local_file_response
from app.core.permissions import require_permission
from app.core.response import success
from app.services import affairs_funding_authority_service as authority
from app.services import affairs_funding_export_service as funding_export
from app.services.affairs_funding_scan_guard import install as install_funding_scan_guard

Money = condecimal(max_digits=14, decimal_places=2, gt=0)

router = APIRouter(prefix="/student-affairs/funding", tags=["学工中心·资助金额权威化"])

# 旧公示扫描 URL 保持不变，只替换运行时服务为逐申请事务版本。
install_funding_scan_guard()


class AmountAdjustmentCreate(BaseModel):
    amount: Money
    reason: str = Field(..., min_length=5, max_length=500)
    version: int = Field(..., ge=0, description="资助申请当前乐观锁版本")


class AmountAdjustmentReview(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    reason: str = Field(..., min_length=5, max_length=500)
    applicationVersion: int = Field(..., ge=0, description="资助申请当前乐观锁版本")


class FundingDisbursementExportBody(BaseModel):
    purpose: str = Field(..., min_length=5, max_length=500, description="导出用途，写入水印和安全审计")
    batchId: int | None = Field(None, ge=1)
    bankStatus: str | None = Field(None, max_length=30)


class FundingDisbursementExportTicketBody(BaseModel):
    expectedVersion: int = Field(..., ge=0)


@router.get("/applications/{application_id}/amount-adjustments", summary="金额调整与双人复核历史")
def list_amount_adjustments(
    application_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.view")),
):
    return success({"items": authority.list_adjustments(application_id, user)})


@router.post("/applications/{application_id}/amount-adjustments", summary="申请调整规则批准金额")
def create_amount_adjustment(
    body: AmountAdjustmentCreate,
    application_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.approve")),
):
    return success(
        authority.request_adjustment(
            application_id, user, body.amount, body.reason, body.version,
        ),
        message="金额调整已提交，须由另一名授权人员复核",
    )


@router.post("/amount-adjustments/{adjustment_id}/review", summary="复核金额调整（申请人与复核人分离）")
def review_amount_adjustment(
    body: AmountAdjustmentReview,
    adjustment_id: int = Path(..., ge=1),
    user=Depends(require_permission("studentAffairs.funding.publicity.manage")),
):
    return success(
        authority.review_adjustment(
            adjustment_id, user, body.action, body.reason, body.applicationVersion,
        ),
        message="金额调整复核已完成",
    )


@router.post("/disbursements/export", summary="创建资助发放台账异步 XLSX 导出任务")
def create_disbursement_export(
    body: FundingDisbursementExportBody,
    user=Depends(require_permission("studentAffairs.funding.disburse.manage")),
):
    return success(
        funding_export.create_job(
            user,
            batch_id=body.batchId,
            bank_status=body.bankStatus,
            purpose=body.purpose,
        ),
        message="导出任务已创建",
    )


@router.get("/disbursements/export-jobs/{job_id}", summary="资助发放台账导出任务详情")
def get_disbursement_export(
    job_id: str = Path(...),
    user=Depends(require_permission("studentAffairs.funding.disburse.manage")),
):
    return success(funding_export.get_job(job_id, user))


@router.post("/disbursements/export-jobs/{job_id}/download-ticket", summary="创建资助发放台账一次性下载票据")
def create_disbursement_export_ticket(
    body: FundingDisbursementExportTicketBody,
    job_id: str = Path(...),
    user=Depends(require_permission("studentAffairs.funding.disburse.manage")),
):
    return success(funding_export.create_download_ticket(job_id, body.expectedVersion, user))


@router.get("/disbursements/export-jobs/{job_id}/download", summary="使用一次性票据下载资助发放台账")
def download_disbursement_export(
    job_id: str = Path(...),
    ticket: str = Query(..., min_length=20),
    user=Depends(require_permission("studentAffairs.funding.disburse.manage")),
):
    path, filename = funding_export.consume_download_ticket(job_id, ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        audit_action="AFFAIRS_FUNDING_DISBURSEMENT_EXPORT_DOWNLOAD",
        audit_target=f"funding-disbursement-export:{job_id}",
        audit_detail={"jobId": str(job_id), "ticketConsumed": True},
    )
