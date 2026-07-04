"""
简化导入导出占位（P0 基线）
────────────────────────────────────────────────────────────
POST /api/v1/import/validate-placeholder
POST /api/v1/export/create-placeholder

与 app/api/v1/transfer.py（/api/v1/admin/students/import|export，正式两步契约
对齐 docs/api/02 §2.12/2.13/2.14）并存：本文件提供扁平化最小占位接口，
不解析真实文件、不生成真实导出，仅回写结构 + 埋审计点，便于 P0 基线联调与测试。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.core.response import success
from app.core.security import get_current_user
from app.schemas.placeholder import ExportCreateRequest, ImportValidateRequest
from app.services import audit_log

import_router = APIRouter(tags=["S10·简化-导入导出"])
export_router = APIRouter(tags=["S10·简化-导入导出"])


@import_router.post("/validate-placeholder", summary="导入校验占位（简化）")
def validate_placeholder(body: ImportValidateRequest, user=Depends(get_current_user)):
    rows = body.rows or []
    result = {
        "bizType": body.bizType,
        "fileId": body.fileId,
        "totalRows": len(rows),
        "validRows": len(rows),
        "errorRows": 0,
        "errors": [],
        "status": "VALIDATED_PLACEHOLDER",
    }
    audit_log.record("IMPORT_VALIDATE", f"import:{body.bizType}", {"fileId": body.fileId})
    return success(result)


@export_router.post("/create-placeholder", summary="导出创建占位（简化）")
def create_placeholder(body: ExportCreateRequest, user=Depends(get_current_user)):
    task_id = f"export-{uuid.uuid4().hex[:12]}"
    audit_log.record("EXPORT", f"export:{task_id}",
                     {"bizType": body.bizType, "fileFormat": body.fileFormat})
    return success({
        "taskId": task_id,
        "status": "READY",
        "fileFormat": body.fileFormat,
        "downloadUrl": f"/mock-storage/{task_id}.{body.fileFormat}?sign=placeholder&expires=900",
        "expiresIn": 900,
    })


@import_router.post("/confirm-placeholder", summary="导入确认占位（简化：Dry-Run 通过后整批确认）")
def confirm_placeholder(user=Depends(get_current_user)):
    batch_id = f"imp-{uuid.uuid4().hex[:8]}"
    audit_log.record("IMPORT", method="POST", path="/api/v1/import/confirm-placeholder",
                     status_code=200, target_type="import", target_id=batch_id)
    return success({
        "batchId": batch_id, "status": "CONFIRMED",
        "notice": "占位实现：未真正写库；接库后按 t_student_import_batch 整批事务执行",
    }, message="导入已确认（占位）")


_EXPORT_TASKS: dict[str, dict] = {}


@export_router.get("/tasks/{task_id}", summary="导出任务状态占位")
def export_task_status(task_id: str, user=Depends(get_current_user)):
    task = _EXPORT_TASKS.get(task_id) or {
        "taskId": task_id, "status": "SUCCESS", "fileUrl": None,
        "securityNotice": "导出含学生信息，需审计、水印、权限控制；文件下载走短期签名 URL（预留 MinIO/OSS：bucket/objectKey/signedUrl 字段）",
        "storage": {"bucket": None, "objectKey": None, "signedUrl": None},
    }
    return success(task)


# ── P4 · 真实导入导出（学生主档）──
from typing import Optional  # noqa: E402

from fastapi import File, UploadFile  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.services import import_export_service as ie  # noqa: E402
from app.services.file_service import validate_ext  # noqa: E402


class ImportRowsRequest(BaseModel):
    rows: list[dict] = Field(default_factory=list, description="学生行（studentNo/realName/gender/grade/phone）")


class ImportConfirmRequest(BaseModel):
    batchNo: str = Field(..., description="Dry-Run 返回的批次号")


class ExportStudentsRequest(BaseModel):
    purpose: str = Field(..., min_length=1, description="导出用途（必填；最小长度由平台规则 export.exportPurposeMinLength 决定，默认 5）")


@import_router.post("/students/validate", summary="学生导入 · Dry-Run 校验（JSON 行）")
def import_students_validate(body: ImportRowsRequest, user=Depends(get_current_user)):
    result = ie.dry_run(body.rows)
    audit_log.record("IMPORT", "student-dry-run",
                     detail={"batchNo": result["batchNo"], "total": result["totalRows"], "errors": result["errorRows"]})
    return success(result, message="校验完成")


@import_router.post("/students/validate-file", summary="学生导入 · Dry-Run 校验（上传 xlsx/csv 文件）")
async def import_students_validate_file(file: UploadFile = File(...), user=Depends(get_current_user)):
    ext = validate_ext(file.filename or "")
    content = await file.read()
    rows = ie.parse_upload_rows(content, ext)
    result = ie.dry_run(rows)
    audit_log.record("IMPORT", "student-dry-run-file",
                     detail={"file": file.filename, "batchNo": result["batchNo"], "total": result["totalRows"]})
    return success(result, message="文件解析并校验完成")


@import_router.post("/students/confirm", summary="学生导入 · 确认写入（整批一个事务，失败回滚）")
def import_students_confirm(body: ImportConfirmRequest, user=Depends(get_current_user)):
    result = ie.confirm(body.batchNo)
    audit_log.record("IMPORT", "student-confirm",
                     detail={"batchNo": body.batchNo, "inserted": result["insertedRows"]})
    return success(result, message="导入完成")


@export_router.post("/students", summary="学生主档导出（真实 xlsx：脱敏 + 水印 + t_export_task + 审计）")
def export_students(body: ExportStudentsRequest, user=Depends(get_current_user)):
    from app.core.exceptions import AppException
    from app.core.token_store import rate_limit
    if not rate_limit(f"export:{user.get('userId', '-')}", 5, 60):
        raise AppException("RATE_LIMITED", "导出过于频繁（每分钟最多 5 次），请稍后再试")
    task = ie.create_students_export(body.purpose)
    audit_log.record("EXPORT", "students-xlsx",
                     detail={"taskId": task["taskId"], "rows": task["rowCount"], "purpose": task["purpose"]})
    return success(task, message="导出完成")


@export_router.get("/tasks/{task_id}/download", summary="下载导出文件（xlsx；下载行为写审计）")
def download_export(task_id: str, user=Depends(get_current_user)):
    path = ie.export_file_path(task_id)
    audit_log.record("DOWNLOAD", "export-file", detail={"taskId": task_id, "file": path.name})
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
