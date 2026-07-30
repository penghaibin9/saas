"""教务数据交换中心路由（阶段 7）。

新路由与旧同步导入导出接口并存到阶段 10；教师 PC 新页面只调用本路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppException
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
from app.services import data_exchange_job_service as jobs

router = APIRouter(prefix="/academic-affairs/file-exchange", tags=["教务中心·数据交换"])

_MAX_FILE_BYTES = 20 * 1024 * 1024


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)


class RosterExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(..., min_length=5, max_length=500)
    keyword: str | None = Field(None, max_length=100)
    status: str | None = Field(None, max_length=32)


class TicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(..., ge=0)
    reason: str = Field(..., min_length=5, max_length=500)


async def _read_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > _MAX_FILE_BYTES:
            raise AppException("FILE_TOO_LARGE", "学籍导入文件超过 20MB，请拆分后重试")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise AppException("VALIDATION_ERROR", "导入文件不能为空")
    await file.seek(0)
    return content


@router.post("/roster/import-jobs", summary="上传学籍 XLSX 并创建服务端权威 ImportJob")
async def create_roster_import_job(
    file: UploadFile = File(...),
    user=Depends(require_permission("academicAffairs.roster.import")),
):
    from app.services import file_service

    content = await _read_upload(file)
    meta = await file_service.store_upload(
        file,
        biz_type="ACADEMIC_ROSTER_IMPORT_SOURCE",
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    item = exchange.create_roster_import_job(
        content=content,
        filename=file.filename or "roster_import.xlsx",
        source_file_id=int(meta["fileId"]),
        user=user,
    )
    return success(item, message="学籍文件已进入安全检查，服务端预检任务已保存")


@router.post("/imports/{job_id}/confirm", summary="仅按 jobId + expectedVersion 确认教务导入")
def confirm_import(
    job_id: str,
    body: ConfirmRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(require_any_permission(
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
        "academicAffairs.grade.input",
    )),
):
    from app.services.data_exchange_confirm_service import confirm_import_job

    result = confirm_import_job(
        job_id,
        expected_version=body.expectedVersion,
        user=user,
        idempotency_key=idempotency_key,
    )
    return success(result, message="教务导入任务已确认完成")


@router.post("/roster/export-jobs", summary="创建可过期、可撤销的学籍名册 ExportJob")
def create_roster_export_job(
    body: RosterExportRequest,
    user=Depends(require_permission("academicAffairs.roster.export")),
):
    return success(exchange.create_roster_export_job(
        user=user,
        purpose=body.purpose,
        keyword=body.keyword,
        status=body.status,
    ), message="学籍名册导出任务已生成")


@router.get("/jobs", summary="当前操作者的教务导入导出任务")
def list_jobs(
    jobType: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(require_any_permission(
        "academicAffairs.roster.import",
        "academicAffairs.roster.export",
        "academicAffairs.grade.import",
        "academicAffairs.grade.input",
    )),
):
    return success(exchange.list_academic_jobs(
        user=user,
        job_type=jobType,
        status=status,
        page=page,
        page_size=pageSize,
    ))


@router.get("/imports/{job_id}", summary="教务导入任务详情")
def import_detail(
    job_id: str,
    user=Depends(require_any_permission(
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
        "academicAffairs.grade.input",
    )),
):
    return success(jobs.get_import_job(job_id, user=user))


@router.get("/exports/{job_id}", summary="教务导出任务详情")
def export_detail(
    job_id: str,
    user=Depends(require_permission("academicAffairs.roster.export")),
):
    return success(jobs.get_export_job(job_id, user=user))


@router.post("/exports/{job_id}/download-ticket", summary="创建教务导出短时一次性下载票据")
def create_download_ticket(
    job_id: str,
    body: TicketRequest,
    user=Depends(require_permission("academicAffairs.roster.export")),
):
    return success(jobs.create_download_ticket(
        job_id,
        expected_version=body.expectedVersion,
        user=user,
    ))


@router.get("/exports/{job_id}/download", summary="使用一次性票据下载教务导出文件")
def download_export(
    job_id: str,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_permission("academicAffairs.roster.export")),
):
    path, filename = jobs.consume_download_ticket(job_id, ticket, user=user)
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/exports/{job_id}/revoke", summary="撤销教务导出任务")
def revoke_export(
    job_id: str,
    body: RevokeRequest,
    user=Depends(require_permission("academicAffairs.roster.export")),
):
    return success(jobs.revoke_export_job(
        job_id,
        expected_version=body.expectedVersion,
        reason=body.reason,
        user=user,
    ), message="教务导出任务已撤销")
