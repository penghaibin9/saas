"""
简化导入导出占位（P0 基线）+ P4 真实学生/6域导入导出。
所有端点仅教职工/管理员可用（require_staff）：防止学生越权导出全校台账。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Header

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.core.idempotency import begin as idempotency_begin, finish as idempotency_finish
from app.core.response import success
from app.core.security import require_staff
from app.schemas.placeholder import ExportCreateRequest, ImportValidateRequest
from app.services import audit_log

import_router = APIRouter(tags=["S10·简化-导入导出"])
export_router = APIRouter(tags=["S10·简化-导入导出"])


@import_router.post("/validate-placeholder", summary="导入校验占位（简化）")
def validate_placeholder(body: ImportValidateRequest, user=Depends(require_staff)):
    rows = body.rows or []
    result = {
        "bizType": body.bizType, "fileId": body.fileId,
        "totalRows": len(rows), "validRows": len(rows), "errorRows": 0,
        "errors": [], "status": "VALIDATED_PLACEHOLDER",
    }
    audit_log.record("IMPORT_VALIDATE", f"import:{body.bizType}", {"fileId": body.fileId})
    return success(result)


@export_router.post("/create-placeholder", summary="导出创建占位（简化）")
def create_placeholder(body: ExportCreateRequest, user=Depends(require_staff)):
    task_id = f"export-{uuid.uuid4().hex[:12]}"
    audit_log.record("EXPORT", f"export:{task_id}",
                     {"bizType": body.bizType, "fileFormat": body.fileFormat})
    return success({
        "taskId": task_id, "status": "READY", "fileFormat": body.fileFormat,
        "downloadUrl": f"/mock-storage/{task_id}.{body.fileFormat}?sign=placeholder&expires=900",
        "expiresIn": 900,
    })


@import_router.post("/confirm-placeholder", summary="导入确认占位（简化）")
def confirm_placeholder(user=Depends(require_staff)):
    batch_id = f"imp-{uuid.uuid4().hex[:8]}"
    audit_log.record("IMPORT", method="POST", path="/api/v1/import/confirm-placeholder",
                     status_code=200, target_type="import", target_id=batch_id)
    return success({
        "batchId": batch_id, "status": "CONFIRMED",
        "notice": "占位实现：未真正写库；接库后按 t_student_import_batch 整批事务执行",
    }, message="导入已确认（占位）")


_EXPORT_TASKS: dict[str, dict] = {}


@export_router.get("/tasks/{task_id}", summary="导出任务状态占位")
def export_task_status(task_id: str, user=Depends(require_staff)):
    task = _EXPORT_TASKS.get(task_id) or {
        "taskId": task_id, "status": "SUCCESS", "fileUrl": None,
        "securityNotice": "导出含学生信息，需审计、水印、权限控制；文件下载走短期签名 URL",
        "storage": {"bucket": None, "objectKey": None, "signedUrl": None},
    }
    return success(task)


# ── P4 · 真实导入导出（学生主档 + 6 域通用）──
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
    purpose: str = Field(..., min_length=1, description="导出用途（必填；最小长度由平台规则决定，默认 5）")


def _limit_operation(user: dict, operation: str, *, user_limit: int, tenant_limit: int) -> None:
    from app.core.token_store import rate_limit
    tenant_id = str(current_tenant_id() or user.get("tenantId") or "-")
    user_id = str(user.get("userId") or "-")
    if not rate_limit(f"{operation}:tenant:{tenant_id}", tenant_limit, 60):
        raise AppException("RATE_LIMITED", f"当前学校{operation}任务过多，请稍后再试")
    if not rate_limit(f"{operation}:tenant:{tenant_id}:user:{user_id}", user_limit, 60):
        raise AppException("RATE_LIMITED", f"操作过于频繁（每分钟最多 {user_limit} 次），请稍后再试")


@import_router.post("/students/validate", summary="学生导入 · Dry-Run 校验（JSON 行）")
def import_students_validate(body: ImportRowsRequest, user=Depends(require_staff)):
    result = ie.dry_run(body.rows)
    audit_log.record("IMPORT", "student-dry-run",
                     detail={"batchNo": result["batchNo"], "total": result["totalRows"], "errors": result["errorRows"]})
    return success(result, message="校验完成")


@import_router.post("/students/validate-file", summary="学生导入 · Dry-Run 校验（上传 xlsx/csv）")
async def import_students_validate_file(file: UploadFile = File(...), user=Depends(require_staff)):
    ext = validate_ext(file.filename or "")
    # 流式读取 + 大小上限，避免超大文件一次性读入内存造成 DoS（导入文件 20MB 足够）。
    _MAX_IMPORT_BYTES = 20 * 1024 * 1024
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > _MAX_IMPORT_BYTES:
            raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
        chunks.append(chunk)
    rows = ie.parse_upload_rows(b"".join(chunks), ext)
    result = ie.dry_run(rows)
    audit_log.record("IMPORT", "student-dry-run-file",
                     detail={"file": file.filename, "batchNo": result["batchNo"], "total": result["totalRows"]})
    return success(result, message="文件解析并校验完成")


@import_router.post("/students/confirm", summary="学生导入 · 确认写入（整批一个事务，失败回滚）")
def import_students_confirm(body: ImportConfirmRequest, user=Depends(require_staff),
                            idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    cached, handle = idempotency_begin(user, "student-import-confirm", idempotency_key,
                                       {"batchNo": body.batchNo})
    if cached is not None:
        return success(cached, message="导入完成（幂等重放）")
    _limit_operation(user, "import-confirm", user_limit=10, tenant_limit=30)
    result = ie.confirm(body.batchNo)
    audit_log.record("IMPORT", "student-confirm",
                     detail={"batchNo": body.batchNo, "inserted": result["insertedRows"]})
    idempotency_finish(handle, result)
    return success(result, message="导入完成")


@import_router.post("/domain/{domain}/validate", summary="6 域通用导入 Dry-Run 校验")
def import_domain_validate(domain: str, body: dict = Body(...), user=Depends(require_staff)):
    from app.services import domain_import_service
    result = domain_import_service.dry_run(domain, body.get("rows") or [])
    audit_log.record("IMPORT", f"{domain}-dry-run", detail={"batchNo": result["batchNo"], "errors": result["errorRows"]})
    return success(result, message="校验完成")


@import_router.post("/domain/confirm", summary="6 域通用导入确认写入")
def import_domain_confirm(body: dict = Body(...), user=Depends(require_staff),
                          idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    from app.services import domain_import_service
    batch_no = str(body.get("batchNo") or "")
    cached, handle = idempotency_begin(user, "domain-import-confirm", idempotency_key,
                                       {"batchNo": batch_no})
    if cached is not None:
        return success(cached, message="导入完成（幂等重放）")
    _limit_operation(user, "import-confirm", user_limit=10, tenant_limit=30)
    result = domain_import_service.confirm(batch_no)
    audit_log.record("IMPORT", "domain-confirm", detail={"batchNo": body.get("batchNo"), "inserted": result["insertedRows"]})
    idempotency_finish(handle, result)
    return success(result, message="导入完成")


@export_router.post("/domain/{domain}", summary="6 域通用导出（xlsx 脱敏+水印+审计+限流）")
def export_domain(domain: str, body: dict = Body(default={}), user=Depends(require_staff),
                  idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    from app.services import domain_export_service
    purpose = str(body.get("purpose") or "")
    cached, handle = idempotency_begin(user, "domain-export", idempotency_key,
                                       {"domain": domain, "purpose": purpose})
    if cached is not None:
        return success(cached, message="导出完成（幂等重放）")
    _limit_operation(user, "export", user_limit=5, tenant_limit=20)
    task = domain_export_service.export_domain(domain, purpose)
    audit_log.record("EXPORT", f"{domain}-xlsx", detail={"taskId": task["taskId"], "rows": task["rowCount"]})
    idempotency_finish(handle, task)
    return success(task, message="导出完成")


@export_router.post("/students", summary="学生主档导出（真实 xlsx：脱敏 + 水印 + 审计 + 限流）")
def export_students(body: ExportStudentsRequest, user=Depends(require_staff),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    cached, handle = idempotency_begin(user, "student-export", idempotency_key,
                                       {"purpose": body.purpose})
    if cached is not None:
        return success(cached, message="导出完成（幂等重放）")
    _limit_operation(user, "export", user_limit=5, tenant_limit=20)
    task = ie.create_students_export(body.purpose)
    audit_log.record("EXPORT", "students-xlsx",
                     detail={"taskId": task["taskId"], "rows": task["rowCount"], "purpose": task["purpose"]})
    idempotency_finish(handle, task)
    return success(task, message="导出完成")


@export_router.get("/tasks/{task_id}/download", summary="下载导出文件（xlsx；下载行为写审计）")
def download_export(task_id: str, user=Depends(require_staff)):
    path = ie.export_file_path(task_id)
    audit_log.record("DOWNLOAD", "export-file", detail={"taskId": task_id, "file": path.name})
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
