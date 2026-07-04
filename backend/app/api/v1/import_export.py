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
