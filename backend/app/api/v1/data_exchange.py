"""学校端统一数据交换任务中心 API（阶段 3）。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.v1.file_contract import validated_local_file_response
from app.core.context import current_tenant_id
from app.core.exceptions import not_found
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.services import data_exchange_job_service as jobs
from app.services.identity_import_scan_orchestrator import (
    create_identity_import_scan_job,
    refresh_identity_import_job,
)

router = APIRouter(prefix="/data-exchange", tags=["系统管理·数据交换任务中心"])


class ConfirmImportRequest(BaseModel):
    """禁止携带 rows/batchNo；服务端只认已保存 Job。"""

    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)


class DownloadTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)


class RevokeExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)
    reason: str = Field(..., min_length=5, max_length=500)


class AdoptAdapterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceFileId: int | None = None


def _identity_job_message(item: dict) -> str:
    status = str(item.get("status") or "").upper()
    if status == "SCANNING":
        return "文件已进入安全扫描；通过后服务端自动解析预检"
    if status == "PARSING":
        return "文件安全扫描已通过，服务端正在解析预检"
    if status == "VALIDATED":
        return "文件安全扫描与服务端预检已通过"
    if status == "VALIDATION_FAILED":
        return "服务端预检存在错误，请查看任务详情或下载错误回执"
    return "身份导入任务已创建"


@router.post("/imports/identity/{kind}/validate-file", summary="上传学生/教师 XLSX 并创建扫描后解析任务")
async def validate_identity_import(
    kind: Literal["students", "teachers"],
    file: UploadFile = File(...),
    user=Depends(require_permission("systemAdmin.user.import")),
):
    from app.core.import_export_auth import enforce_student_import
    from app.services import file_service

    import_kind = "STUDENT" if kind == "students" else "TEACHER"
    if import_kind == "STUDENT":
        enforce_student_import(user)
    # 唯一顺序：流式落隔离区 -> FileObject 扫描 -> 路径型 openpyxl 解析 -> 预检批次。
    file_meta = await file_service.store_upload(
        file,
        biz_type="DATA_IMPORT_SOURCE",
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    item = create_identity_import_scan_job(
        kind=import_kind,
        source_file_id=int(file_meta["fileId"]),
        filename=file.filename or f"{kind}.xlsx",
        user=user,
    )
    return success(item, message=_identity_job_message(item))


@router.post("/imports/{job_id}/confirm", summary="按 jobId + expectedVersion 确认导入")
def confirm_import(
    job_id: str,
    body: ConfirmImportRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.migration.import",
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
    )),
):
    from app.services.data_exchange_confirm_service import confirm_import_job

    return success(
        confirm_import_job(
            job_id,
            expected_version=body.expectedVersion,
            user=user,
            idempotency_key=idempotency_key,
        ),
        message="导入任务已确认完成",
    )


@router.post("/imports/adapters/migration/{batch_no}", summary="将真实老系统迁移批次接入统一任务中心")
def adopt_migration_batch(
    batch_no: str,
    body: AdoptAdapterRequest,
    user=Depends(require_permission("systemAdmin.migration.import")),
):
    from app.models import StudentImportBatch

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(StudentImportBatch).where(
            StudentImportBatch.tenant_id == current_tenant_id(),
            StudentImportBatch.batch_no == batch_no,
            StudentImportBatch.is_deleted.is_(False),
        )).first()
        if not row or not str(row.remark or "").startswith("migration:"):
            raise not_found("迁移批次不存在")
        status_map = {
            "SUCCESS": "SUCCEEDED",
            "CONFIRMED": "CONFIRMING",
            "DRY_RUN_FAILED": "VALIDATION_FAILED",
            "FAILED": "FAILED",
        }
        item = jobs.register_legacy_import_adapter(
            adapter_type=jobs.IMPORT_ADAPTER_MIGRATION,
            adapter_ref=row.batch_no,
            module_code="SYSTEM",
            import_type=str(row.remark or "migration:UNKNOWN").split(":", 1)[-1],
            source_file_id=body.sourceFileId or row.file_id,
            total_rows=int(row.total_rows or 0),
            valid_rows=max(0, int(row.total_rows or 0) - int(row.error_rows or 0)),
            invalid_rows=int(row.error_rows or 0),
            status=status_map.get(str(row.status or "").upper(), "VALIDATED"),
            snapshot={"legacyTable": "t_student_import_batch", "legacyStatus": row.status},
            user=user,
        )
        return success(item, message="迁移批次已接入统一任务中心")
    finally:
        db.close()


@router.post("/imports/adapters/excel/{legacy_job_id}", summary="将真实公共 Excel 作业接入统一任务中心")
def adopt_excel_job(
    legacy_job_id: int,
    body: AdoptAdapterRequest,
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
    )),
):
    from app.models import ExcelImportJob

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(ExcelImportJob).where(
            ExcelImportJob.id == legacy_job_id,
            ExcelImportJob.tenant_id == current_tenant_id(),
            ExcelImportJob.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("Excel 导入作业不存在")
        status_map = {
            "IMPORTED": "SUCCEEDED",
            "VALIDATED": "VALIDATED",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
        }
        item = jobs.register_legacy_import_adapter(
            adapter_type=jobs.IMPORT_ADAPTER_EXCEL,
            adapter_ref=str(row.id),
            module_code=row.module_key,
            import_type=row.biz_type,
            source_file_id=body.sourceFileId,
            total_rows=int(row.total_rows or 0),
            valid_rows=int(row.valid_rows or 0),
            invalid_rows=int(row.invalid_rows or 0),
            status=status_map.get(str(row.status or "").upper(), str(row.status or "VALIDATED").upper()),
            snapshot={
                "legacyTable": "t_excel_import_job",
                "fileName": row.file_name,
                "fileSha256": row.file_sha256,
                "dataScope": row.data_scope_snapshot or {},
            },
            user=user,
        )
        return success(item, message="Excel 作业已接入统一任务中心")
    finally:
        db.close()


@router.get("/jobs", summary="学校端导入导出任务列表")
def list_data_exchange_jobs(
    jobType: str = Query(""),
    status: str = Query(""),
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.migration.view",
        "systemAdmin.audit.sensitive.view",
    )),
):
    return success(jobs.list_jobs(
        user=user,
        job_type=jobType,
        status=status,
        keyword=keyword,
        page=page,
        page_size=pageSize,
    ))


@router.get("/imports/{job_id}", summary="导入任务详情并推进扫描后预检")
def import_job_detail(
    job_id: str,
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.migration.view",
        "systemAdmin.audit.sensitive.view",
    )),
):
    item = refresh_identity_import_job(job_id, user=user)
    return success(item, message=_identity_job_message(item))


@router.get("/exports/{job_id}", summary="导出任务详情")
def export_job_detail(
    job_id: str,
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.audit.sensitive.view",
    )),
):
    return success(jobs.get_export_job(job_id, user=user))


@router.post("/exports/{job_id}/download-ticket", summary="创建短时一次性下载票据")
def export_download_ticket(
    job_id: str,
    body: DownloadTicketRequest,
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.audit.sensitive.view",
    )),
):
    return success(jobs.create_download_ticket(
        job_id,
        expected_version=body.expectedVersion,
        user=user,
    ))


@router.get("/exports/{job_id}/download", summary="使用一次性票据下载导出文件")
def download_export_file(
    job_id: str,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.audit.sensitive.view",
    )),
):
    path, filename = jobs.consume_download_ticket(job_id, ticket, user=user)
    media_type = (
        "application/zip" if str(filename).lower().endswith(".zip")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return validated_local_file_response(
        path,
        filename=filename,
        media_type=media_type,
        audit_action="DATA_EXCHANGE_EXPORT_DOWNLOAD",
        audit_target=f"data-exchange-export:{job_id}",
        audit_detail={"jobId": str(job_id), "ticketConsumed": True},
    )


@router.post("/exports/{job_id}/revoke", summary="撤销导出任务并使票据失效")
def revoke_export_file(
    job_id: str,
    body: RevokeExportRequest,
    user=Depends(require_any_permission(
        "systemAdmin.user.import",
        "systemAdmin.audit.sensitive.view",
    )),
):
    return success(
        jobs.revoke_export_job(
            job_id,
            expected_version=body.expectedVersion,
            reason=body.reason,
            user=user,
        ),
        message="导出任务已撤销",
    )
