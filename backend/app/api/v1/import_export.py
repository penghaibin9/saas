"""
导入导出：学生主档 + 域白名单通用导入导出。
真实端点强制 permissionCode；占位端点仅非生产注册（见 router 条件挂载时由本文件内部再闸一道）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Header

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.idempotency import begin as idempotency_begin, finish as idempotency_finish
from app.core.import_export_auth import (
    enforce_export_perm,
    enforce_import_perm,
    enforce_student_export,
    enforce_student_import,
)
from app.core.permissions import require_permission
from app.core.response import success
from app.core.security import require_staff
from app.schemas.placeholder import ExportCreateRequest, ImportValidateRequest
from app.services import audit_log

import_router = APIRouter(tags=["S10·简化-导入导出"])
export_router = APIRouter(tags=["S10·简化-导入导出"])


def _deny_placeholder():
    if settings.is_prod:
        raise not_found("接口不存在")


@import_router.post("/validate-placeholder", summary="导入校验占位（仅非生产）")
def validate_placeholder(body: ImportValidateRequest, user=Depends(require_staff)):
    _deny_placeholder()
    rows = body.rows or []
    result = {
        "bizType": body.bizType, "fileId": body.fileId,
        "totalRows": len(rows), "validRows": len(rows), "errorRows": 0,
        "errors": [], "status": "VALIDATED_PLACEHOLDER",
    }
    audit_log.record("IMPORT_VALIDATE", f"import:{body.bizType}", {"fileId": body.fileId})
    return success(result)


@export_router.post("/create-placeholder", summary="导出创建占位（仅非生产）")
def create_placeholder(body: ExportCreateRequest, user=Depends(require_staff)):
    _deny_placeholder()
    task_id = f"export-{uuid.uuid4().hex[:12]}"
    audit_log.record("EXPORT", f"export:{task_id}",
                     {"bizType": body.bizType, "fileFormat": body.fileFormat})
    return success({
        "taskId": task_id, "status": "READY", "fileFormat": body.fileFormat,
        "downloadUrl": f"/api/v1/export/tasks/{task_id}/download",
        "expiresIn": 900,
        "notice": "占位实现：未生成真实文件；请改用 POST /export/students 或 /export/domain/{domain}",
    })


@import_router.post("/confirm-placeholder", summary="导入确认占位（仅非生产）")
def confirm_placeholder(user=Depends(require_staff)):
    _deny_placeholder()
    batch_id = f"imp-{uuid.uuid4().hex[:8]}"
    audit_log.record("IMPORT", method="POST", path="/api/v1/import/confirm-placeholder",
                     status_code=200, target_type="import", target_id=batch_id)
    return success({
        "batchId": batch_id, "status": "CONFIRMED",
        "notice": "占位实现：未真正写库；请改用 POST /import/students/confirm",
    }, message="导入已确认（占位）")


_EXPORT_TASKS: dict[str, dict] = {}


@export_router.get("/tasks/{task_id}", summary="导出任务状态")
def export_task_status(task_id: str, user=Depends(require_staff)):
    task = _EXPORT_TASKS.get(task_id)
    if not task:
        # 不猜测成功：未知任务统一 404，避免泄露
        raise not_found("导出任务不存在或文件已清理")
    return success(task)


# ── 真实导入导出（学生主档 + 域白名单）──
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
def import_students_validate(body: ImportRowsRequest,
                             user=Depends(require_permission("student.import"))):
    enforce_student_import(user)
    result = ie.dry_run(body.rows)
    audit_log.record("IMPORT", "student-dry-run",
                     detail={"batchNo": result["batchNo"], "total": result["totalRows"], "errors": result["errorRows"]})
    return success(result, message="校验完成")


@import_router.post("/students/validate-file", summary="学生导入 · Dry-Run 校验（上传 xlsx/csv）")
async def import_students_validate_file(file: UploadFile = File(...),
                                        user=Depends(require_permission("student.import"))):
    enforce_student_import(user)
    ext = validate_ext(file.filename or "")
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
def import_students_confirm(body: ImportConfirmRequest,
                            user=Depends(require_permission("student.import")),
                            idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    enforce_student_import(user)
    ie.assert_confirm_allowed(user, "STUDENT_PROFILE", body.batchNo, "student.import")
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


@import_router.post("/domain/{domain}/validate", summary="域白名单通用导入 Dry-Run 校验")
def import_domain_validate(domain: str, body: dict = Body(...), user=Depends(require_staff)):
    from app.services import domain_import_service
    auth = enforce_import_perm(user, domain)
    result = domain_import_service.dry_run(auth.domain, body.get("rows") or [],
                                           namespace=auth.import_namespace, user=user)
    audit_log.record("IMPORT", f"{auth.domain}-dry-run",
                     detail={"batchNo": result["batchNo"], "errors": result["errorRows"]})
    return success(result, message="校验完成")


@import_router.post("/domain/confirm", summary="域白名单通用导入确认写入")
def import_domain_confirm(body: dict = Body(...), user=Depends(require_staff),
                          idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    from app.services import domain_import_service
    batch_no = str(body.get("batchNo") or "")
    domain = str(body.get("domain") or "")
    if not domain:
        # 从批次反查 domain，禁止无域确认
        meta = domain_import_service.peek_batch(batch_no)
        domain = (meta or {}).get("domain") or ""
    auth = enforce_import_perm(user, domain)
    domain_import_service.assert_confirm_allowed(user, batch_no, auth)
    cached, handle = idempotency_begin(user, "domain-import-confirm", idempotency_key,
                                       {"batchNo": batch_no})
    if cached is not None:
        return success(cached, message="导入完成（幂等重放）")
    _limit_operation(user, "import-confirm", user_limit=10, tenant_limit=30)
    result = domain_import_service.confirm(batch_no)
    audit_log.record("IMPORT", "domain-confirm",
                     detail={"batchNo": batch_no, "inserted": result["insertedRows"]})
    idempotency_finish(handle, result)
    return success(result, message="导入完成")


@export_router.post("/domain/{domain}", summary="域白名单通用导出（xlsx 脱敏+水印+审计+限流）")
def export_domain(domain: str, body: dict = Body(default={}), user=Depends(require_staff),
                  idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    from app.services import domain_export_service
    auth = enforce_export_perm(user, domain)
    purpose = str(body.get("purpose") or "")
    cached, handle = idempotency_begin(user, "domain-export", idempotency_key,
                                       {"domain": auth.domain, "purpose": purpose})
    if cached is not None:
        return success(cached, message="导出完成（幂等重放）")
    _limit_operation(user, "export", user_limit=5, tenant_limit=20)
    task = domain_export_service.export_domain(auth.domain, purpose, user=user)
    audit_log.record("EXPORT", f"{auth.domain}-xlsx",
                     detail={"taskId": task["taskId"], "rows": task["rowCount"]})
    idempotency_finish(handle, task)
    return success(task, message="导出完成")


@export_router.post("/students", summary="学生主档导出（真实 xlsx：脱敏 + 水印 + 审计 + 限流）")
def export_students(body: ExportStudentsRequest,
                    user=Depends(require_permission("student.export")),
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    enforce_student_export(user)
    cached, handle = idempotency_begin(user, "student-export", idempotency_key,
                                       {"purpose": body.purpose})
    if cached is not None:
        return success(cached, message="导出完成（幂等重放）")
    _limit_operation(user, "export", user_limit=5, tenant_limit=20)
    task = ie.create_students_export(body.purpose, user=user)
    audit_log.record("EXPORT", "students-xlsx",
                     detail={"taskId": task["taskId"], "rows": task["rowCount"], "purpose": task["purpose"]})
    idempotency_finish(handle, task)
    return success(task, message="导出完成")


@export_router.get("/tasks/{task_id}/download", summary="下载导出文件（xlsx；归属+权限+租户校验）")
def download_export(task_id: str, user=Depends(require_staff)):
    path = ie.export_file_path(task_id, user=user)
    audit_log.record("DOWNLOAD", "export-file", detail={"taskId": task_id, "file": path.name})
    return FileResponse(path, filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
