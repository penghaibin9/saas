"""教务数据交换中心路由（阶段 7 收口）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, Path, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.file_contract import validated_local_file_response
from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.core.security import require_staff
from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
from app.services import data_exchange_job_service as jobs

router = APIRouter(prefix="/academic-affairs/file-exchange", tags=["教务中心·数据交换"])


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


async def _store_import_job(
    *,
    file: UploadFile,
    biz_type: str,
    import_type: str,
    context: dict,
    user: dict,
) -> dict:
    from app.services import file_service

    meta = await file_service.store_upload(
        file,
        biz_type=biz_type,
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    return exchange.create_academic_import_job(
        filename=file.filename or "academic_import.xlsx",
        source_file_id=int(meta["fileId"]),
        import_type=import_type,
        context=context,
        user=user,
    )


def _created_message(item: dict) -> str:
    if item.get("status") == "SCANNING":
        return "文件已进入安全扫描；扫描通过后服务端自动预检"
    if item.get("status") == "VALIDATED":
        return "文件安全检查与服务端预检已通过"
    if item.get("status") == "VALIDATION_FAILED":
        return "文件已完成安全检查，但服务端预检存在错误"
    return "教务导入任务已创建"


@router.post("/roster/import-jobs", summary="上传学籍 XLSX 并创建服务端权威 ImportJob")
async def create_roster_import_job(
    file: UploadFile = File(...),
    user=Depends(require_permission("academicAffairs.roster.import")),
):
    item = await _store_import_job(
        file=file,
        biz_type="ACADEMIC_ROSTER_IMPORT_SOURCE",
        import_type=exchange.ACADEMIC_ROSTER_IMPORT,
        context={},
        user=user,
    )
    return success(item, message=_created_message(item))


@router.post("/grade-tasks/{task_id}/import-jobs", summary="上传成绩 XLSX 并创建服务端权威 ImportJob")
async def create_grade_import_job(
    task_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    user=Depends(require_permission("academicAffairs.grade.input")),
):
    item = await _store_import_job(
        file=file,
        biz_type="ACADEMIC_GRADE_IMPORT_SOURCE",
        import_type=exchange.ACADEMIC_GRADE_IMPORT,
        context={"taskId": task_id},
        user=user,
    )
    return success(item, message=_created_message(item))


@router.post("/schedule-batches/{batch_id}/import-jobs", summary="上传排课结果 XLSX 并创建服务端权威 ImportJob")
async def create_schedule_import_job(
    batch_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    user=Depends(require_permission("academicAffairs.schedule.import")),
):
    item = await _store_import_job(
        file=file,
        biz_type="ACADEMIC_SCHEDULE_IMPORT_SOURCE",
        import_type=exchange.ACADEMIC_SCHEDULE_IMPORT,
        context={"batchId": batch_id},
        user=user,
    )
    return success(item, message=_created_message(item))


@router.post("/imports/{job_id}/confirm", summary="仅按 jobId + expectedVersion 确认教务导入")
def confirm_import(
    job_id: str,
    body: ConfirmRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user=Depends(require_any_permission(
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
        "academicAffairs.grade.input",
        "academicAffairs.schedule.import",
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
    user=Depends(require_staff),
):
    return success(exchange.list_academic_jobs(
        user=user,
        job_type=jobType,
        status=status,
        page=page,
        page_size=pageSize,
    ))


@router.get("/imports/{job_id}", summary="教务导入任务详情并推进扫描后服务端预检")
def import_detail(job_id: str, user=Depends(require_staff)):
    return success(exchange.refresh_import_job(job_id, user=user))


@router.get("/exports/{job_id}", summary="教务导出任务详情")
def export_detail(job_id: str, user=Depends(require_staff)):
    return success(jobs.get_export_job(job_id, user=user))


@router.post("/exports/{job_id}/download-ticket", summary="创建教务导出短时一次性下载票据")
def create_download_ticket(job_id: str, body: TicketRequest, user=Depends(require_staff)):
    return success(jobs.create_download_ticket(
        job_id,
        expected_version=body.expectedVersion,
        user=user,
    ))


@router.get("/exports/{job_id}/download", summary="使用一次性票据下载教务导出文件")
def download_export(
    job_id: str,
    ticket: str = Query(..., min_length=20),
    user=Depends(require_staff),
):
    path, filename = jobs.consume_download_ticket(job_id, ticket, user=user)
    media_type = "application/zip" if str(filename).lower().endswith(".zip") else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return validated_local_file_response(
        path,
        filename=filename,
        media_type=media_type,
        audit_action="ACADEMIC_EXPORT_DOWNLOAD",
        audit_target=f"academic-export:{job_id}",
        audit_detail={"jobId": str(job_id), "ticketConsumed": True},
    )


@router.post("/exports/{job_id}/revoke", summary="撤销教务导出任务")
def revoke_export(job_id: str, body: RevokeRequest, user=Depends(require_staff)):
    return success(jobs.revoke_export_job(
        job_id,
        expected_version=body.expectedVersion,
        reason=body.reason,
        user=user,
    ), message="教务导出任务已撤销")
