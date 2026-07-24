"""
导入导出（占位，对齐 docs/05-数据接口权限与安全/api/02-学生主档 2.12/2.13/2.14）
────────────────────────────────────────────────────────────
导入两步：dry-run（试算校验）→ confirm（幂等确认）。导出返回异步任务占位。
本阶段不解析真实文件、不生成真实导出：只回契约结构，埋审计点。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.response import success
from app.core.security import require_staff
from app.services import audit_log

router = APIRouter(prefix="/admin/students", tags=["02·导入导出（占位）"])


def _tid() -> int:
    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tid = 0
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝写入")
    return tid


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
def import_dry_run(body: DryRunBody, user=Depends(require_staff)):
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
    from app.services import shared_import_batch_service as shared_batches
    shared_batches.create(_tid(), "TRANSFER_PLACEHOLDER", batch_id, "DRY_RUN_PASSED",
                          result, errors=result["errors"],
                          operator_key=str(user.get("userId") or ""))
    audit_log.record("IMPORT_DRY_RUN", f"import:{batch_id}", {"importType": body.importType})
    return success(result)


@router.post("/import/confirm", summary="2.13 导入确认（占位，requestId 幂等）")
def import_confirm(body: ConfirmBody, user=Depends(require_staff)):
    from app.services import shared_import_batch_service as shared_batches
    batch, token, already_done = shared_batches.claim(
        _tid(), "TRANSFER_PLACEHOLDER", body.batchId,
        required_status="DRY_RUN_PASSED", request_id=body.requestId)
    if already_done:
        return success(batch)
    result = {"batchId": body.batchId, "imported": batch["validRows"], "status": "SUCCESS"}
    shared_batches.finish(_tid(), "TRANSFER_PLACEHOLDER", body.batchId, token, result)
    audit_log.record("IMPORT", f"import:{body.batchId}", {"imported": batch["validRows"]})
    return success(result)


@router.post("/export", summary="2.14 导出（占位：返回异步任务）")
def export_students(body: ExportBody, user=Depends(require_staff)):
    task_id = f"export-{uuid.uuid4().hex[:12]}"
    audit_log.record("EXPORT", f"export:{task_id}", {"exportType": body.exportType, "filters": body.filters or {}})
    return success({
        "taskId": task_id, "status": "READY",
        "downloadUrl": f"/mock-storage/{task_id}.xlsx?sign=placeholder&expires=900",
        "expiresIn": 900,
        "note": "占位实现：真实导出接任务队列后生成文件并走文件中心签名 URL",
    })
