"""老系统数据迁移 API（系统管理 · 数据迁移，P1 · 6 域）。

权限：systemAdmin.migration.*（SCHOOL_ADMIN/SYS_ADMIN/平台超管按 ROLE_PERMISSIONS 通配命中，
其余角色 fail-closed）；平台租户迁移进度走 platform.tenant.migration.view（仅平台侧）。
管线：migration_import_service（dry-run → 行级错误 → confirm 整批事务；批次落
t_student_import_batch，remark 前缀 migration:<domain>）。
"""
from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import success
from app.services import audit_log
from app.services import migration_import_service as mig

router = APIRouter(prefix="/system/migration", tags=["系统管理·数据迁移"])
platform_router = APIRouter(prefix="/platform/migration", tags=["平台运营·租户迁移进度"])

_XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MAX_IMPORT_BYTES = 20 * 1024 * 1024


@router.get("/overview", summary="迁移地图：6 域依赖/库内数量/最近批次")
def migration_overview(user=Depends(require_permission("systemAdmin.migration.view"))):
    return success(mig.overview())


@router.get("/batches", summary="迁移批次历史")
def migration_batches(domain: str | None = None,
                      user=Depends(require_permission("systemAdmin.migration.view"))):
    return success(mig.list_batches(domain))


@router.get("/domains/{domain}/template", summary="下载迁移域官方 xlsx 模板")
def migration_template(domain: str,
                       user=Depends(require_permission("systemAdmin.migration.import"))):
    meta = mig.domain_meta(domain)
    filename = f"数据迁移-{meta['label']}模板.xlsx"
    return StreamingResponse(
        io.BytesIO(mig.build_template(domain)), media_type=_XLSX_MT,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/domains/{domain}/validate", summary="迁移域 Dry-Run 校验（JSON 行）")
def migration_validate(domain: str, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.migration.import"))):
    result = mig.dry_run(domain, body.get("rows") or [])
    audit_log.record("IMPORT", f"migration:{domain}-dry-run",
                     detail={"batchNo": result["batchNo"], "total": result["totalRows"],
                             "errors": result["errorRows"]})
    return success(result, message="校验完成")


@router.post("/domains/{domain}/validate-file", summary="迁移域 Dry-Run 校验（上传 xlsx/csv）")
async def migration_validate_file(domain: str, file: UploadFile = File(...),
                                  user=Depends(require_permission("systemAdmin.migration.import"))):
    from app.services.file_service import validate_ext
    from app.services.import_export_service import parse_upload_rows
    ext = validate_ext(file.filename or "")
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > _MAX_IMPORT_BYTES:
            raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
        chunks.append(chunk)
    rows = parse_upload_rows(b"".join(chunks), ext)
    result = mig.dry_run(domain, rows)
    audit_log.record("IMPORT", f"migration:{domain}-dry-run-file",
                     detail={"file": file.filename, "batchNo": result["batchNo"],
                             "total": result["totalRows"], "errors": result["errorRows"]})
    return success(result, message="文件解析并校验完成")


@router.post("/domains/{domain}/errors-xlsx", summary="下载错误行 Excel（rowNo+错误原因）")
def migration_errors_xlsx(domain: str, body: dict = Body(...),
                          user=Depends(require_permission("systemAdmin.migration.import"))):
    from app.services import xlsx_util
    meta = mig.domain_meta(domain)
    headers = [c[1] for c in meta["columns"]]
    keys = [c[0] for c in meta["columns"]]
    rows = body.get("rows") or []
    # 服务端 rowNo 从 2 起（Excel 行号）；错误行 xlsx 底座按 1-based 数据行匹配
    errors = [{**e, "rowNo": max(int(e.get("rowNo") or 2) - 1, 1)} for e in (body.get("errors") or [])]
    content = xlsx_util.build_error_rows_xlsx(
        headers, rows, errors, lambda r: [r.get(k, "") or r.get(t, "") for k, t in zip(keys, headers)])
    return success(xlsx_util.pack_xlsx_result(content, f"数据迁移-{meta['label']}-错误行.xlsx", len(errors)))


@router.post("/confirm", summary="确认导入（整批一个事务，失败回滚）")
def migration_confirm(body: dict = Body(...),
                      user=Depends(require_permission("systemAdmin.migration.import"))):
    batch_no = str(body.get("batchNo") or "").strip()
    result = mig.confirm(batch_no)
    audit_log.record("IMPORT_CONFIRM", f"migration:{result['domain']}",
                     detail={"batchNo": batch_no, "rows": result["insertedRows"]})
    return success(result, message="导入完成")


@platform_router.get("/overview", summary="全部租户迁移进度（平台运营只读聚合）")
def platform_migration_overview(user=Depends(require_permission("platform.tenant.migration.view"))):
    return success(mig.platform_overview())
