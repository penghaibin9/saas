"""
导入导出（占位，对齐 docs/api/02-学生主档 2.12/2.13/2.14）
────────────────────────────────────────────────────────────
导入两步：dry-run（试算校验）→ confirm（幂等确认）。导出返回异步任务占位。
本阶段不解析真实文件、不生成真实导出：只回契约结构，埋审计点。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.exceptions import AppException, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.services import audit_log

router = APIRouter(prefix="/admin/students", tags=["02·导入导出（占位）"])

# 内存批次表：batchId → 状态（接库后为 t_student_import_batch）
_BATCHES: dict[str, dict] = {}
# 幂等：requestId → batchId
_REQUESTS: dict[str, str] = {}


class DryRunBody(BaseModel):
    fileId: str = Field(description="先经 POST /api/v1/files 上传获得")
    importType: str = Field(default="STUDENT_PROFILE")


class ConfirmBody(BaseModel):
    batchId: str
    requestId: str = Field(description="幂等键：相同 requestId 重复提交返回相同结果")


class ExportBody(BaseModel):
    exportType: str = Field(default="STUDENT_PROFILE")
    filters: Optional[dict] = None


@router.post("/import/dry-run", summary="2.12 导入试算 DryRun（占位）")
def import_dry_run(body: DryRunBody, user=Depends(get_current_user)):
    batch_id = f"batch-{uuid.uuid4().hex[:12]}"
    result = {
        "batchId": batch_id, "importType": body.importType, "fileId": body.fileId,
        "totalRows": 50, "validRows": 47, "errorRows": 3,
        "errors": [
            {"row": 5, "field": "idCardNo", "msg": "身份证号格式不正确"},
            {"row": 12, "field": "className", "msg": "班级「软件2409」不存在"},
            {"row": 33, "field": "phone", "msg": "手机号重复"},
        ],
        "status": "DRY_RUN_DONE",
    }
    _BATCHES[batch_id] = {**result, "confirmed": False}
    audit_log.record("IMPORT_DRY_RUN", f"import:{batch_id}", {"importType": body.importType})
    return success(result)


@router.post("/import/confirm", summary="2.13 导入确认（占位，requestId 幂等）")
def import_confirm(body: ConfirmBody, user=Depends(get_current_user)):
    # 幂等：同 requestId 直接返回原结果
    if body.requestId in _REQUESTS:
        prior = _REQUESTS[body.requestId]
        if prior != body.batchId:
            raise AppException("IDEMPOTENCY_CONFLICT", "相同 requestId 提交了不同批次")
        batch = _BATCHES[prior]
        return success({"batchId": prior, "imported": batch["validRows"], "status": "SUCCESS"})

    batch = _BATCHES.get(body.batchId)
    if not batch:
        raise not_found("导入批次不存在，请先执行 dry-run")
    if batch["confirmed"]:
        raise AppException("DATA_CONFLICT", "该批次已确认导入，请勿重复操作")

    batch["confirmed"] = True
    _REQUESTS[body.requestId] = body.batchId
    audit_log.record("IMPORT", f"import:{body.batchId}", {"imported": batch["validRows"]})
    return success({"batchId": body.batchId, "imported": batch["validRows"], "status": "SUCCESS"})


@router.post("/export", summary="2.14 导出（占位：返回异步任务）")
def export_students(body: ExportBody, user=Depends(get_current_user)):
    task_id = f"export-{uuid.uuid4().hex[:12]}"
    audit_log.record("EXPORT", f"export:{task_id}", {"exportType": body.exportType, "filters": body.filters or {}})
    return success({
        "taskId": task_id, "status": "READY",
        "downloadUrl": f"/mock-storage/{task_id}.xlsx?sign=placeholder&expires=900",
        "expiresIn": 900,
        "note": "占位实现：真实导出接任务队列后生成文件并走文件中心签名 URL",
    })
