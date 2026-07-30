"""老系统数据迁移 API（系统管理 · 数据迁移，P1 · 21 域）。

权限：systemAdmin.migration.*；迁移仍复用原业务 dry-run/confirm 事务，阶段 3 新增：
原始 XLSX 进入公共文件中心，预检结果自动登记统一 ImportJob，学校页面只用 jobId 确认。
"""
from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.permissions import require_permission
from app.core.response import success
from app.db.session import get_sessionmaker
from app.services import audit_log
from app.services import migration_import_service as mig

router = APIRouter(prefix="/system/migration", tags=["系统管理·数据迁移"])
platform_router = APIRouter(prefix="/platform/migration", tags=["平台运营·租户迁移进度"])

_XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/overview", summary="迁移地图：21 域依赖/库内数量/最近批次")
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


@router.post("/domains/{domain}/validate", summary="迁移域 Dry-Run 校验（兼容 JSON 行）")
def migration_validate(domain: str, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.migration.import"))):
    result = mig.dry_run(domain, body.get("rows") or [])
    audit_log.record("IMPORT", f"migration:{domain}-dry-run",
                     detail={"batchNo": result["batchNo"], "total": result["totalRows"],
                             "errors": result["errorRows"], "legacyJsonAdapter": True})
    return success(result, message="校验完成；正式学校页面请使用 XLSX 统一任务入口")


@router.post("/domains/{domain}/validate-file", summary="迁移域 XLSX 安全上传、预检并创建统一任务")
async def migration_validate_file(domain: str, file: UploadFile = File(...),
                                  user=Depends(require_permission("systemAdmin.migration.import"))):
    from app.models import StudentImportBatch
    from app.services import data_exchange_job_service as jobs
    from app.services import file_service, xlsx_util
    from app.services.import_export_service import parse_upload_rows

    content = await xlsx_util.read_safe_upload(file)
    rows = parse_upload_rows(content, "xlsx")
    result = mig.dry_run(domain, rows)
    await file.seek(0)
    file_meta = await file_service.store_upload(
        file,
        biz_type="DATA_IMPORT_SOURCE",
        user=user,
        visibility="PRIVATE",
        security_level="SENSITIVE",
    )
    source_file_id = int(file_meta["fileId"])
    tenant_id = int(current_tenant_id() or 0)

    db = get_sessionmaker()()
    try:
        ledger = db.scalars(select(StudentImportBatch).where(
            StudentImportBatch.tenant_id == tenant_id,
            StudentImportBatch.batch_no == result["batchNo"],
            StudentImportBatch.is_deleted.is_(False),
        )).first()
        if ledger:
            ledger.file_id = source_file_id
            db.commit()
    finally:
        db.close()

    status = "VALIDATED" if result["status"] == "DRY_RUN_PASSED" else "VALIDATION_FAILED"
    job = jobs.register_legacy_import_adapter(
        adapter_type=jobs.IMPORT_ADAPTER_MIGRATION,
        adapter_ref=result["batchNo"],
        module_code="SYSTEM",
        import_type=f"MIGRATION_{domain.upper().replace('-', '_')}",
        source_file_id=source_file_id,
        total_rows=int(result["totalRows"]),
        valid_rows=int(result["okRows"]),
        invalid_rows=int(result["errorRows"]),
        status=status,
        snapshot={
            "domain": domain,
            "fileName": file.filename,
            "fileSha256": file_meta.get("sha256"),
            "legacyBatchNo": result["batchNo"],
        },
        user=user,
    )
    audit_log.record("IMPORT", f"migration:{domain}-dry-run-file",
                     detail={"fileId": str(source_file_id), "jobId": job["id"],
                             "batchNo": result["batchNo"], "total": result["totalRows"],
                             "errors": result["errorRows"]})
    return success({
        **result,
        "jobId": job["id"],
        "jobVersion": job["version"],
        "sourceFileId": str(source_file_id),
    }, message="文件已进入安全检查，迁移预检任务已保存")


@router.post("/domains/{domain}/errors-xlsx", summary="下载错误行 Excel（兼容入口）")
def migration_errors_xlsx(domain: str, body: dict = Body(...),
                          user=Depends(require_permission("systemAdmin.migration.import"))):
    from app.services import xlsx_util
    meta = mig.domain_meta(domain)
    headers = [c[1] for c in meta["columns"]]
    keys = [c[0] for c in meta["columns"]]
    rows = body.get("rows") or []
    errors = [{**e, "rowNo": max(int(e.get("rowNo") or 2) - 1, 1)} for e in (body.get("errors") or [])]
    content = xlsx_util.build_error_rows_xlsx(
        headers, rows, errors, lambda r: [r.get(k, "") or r.get(t, "") for k, t in zip(keys, headers)])
    return success(xlsx_util.pack_xlsx_result(content, f"数据迁移-{meta['label']}-错误行.xlsx", len(errors)))


@router.post("/confirm", summary="旧 batchNo 确认兼容接口")
def migration_confirm(body: dict = Body(...),
                      user=Depends(require_permission("systemAdmin.migration.import"))):
    batch_no = str(body.get("batchNo") or "").strip()
    result = mig.confirm(batch_no)
    audit_log.record("IMPORT_CONFIRM", f"migration:{result['domain']}",
                     detail={"batchNo": batch_no, "rows": result["insertedRows"],
                             "legacyCompatibility": True})
    return success(result, message="导入完成；学校页面已迁移到统一 jobId 确认")


@platform_router.get("/overview", summary="全部租户迁移进度（平台运营只读聚合）")
def platform_migration_overview(user=Depends(require_permission("platform.tenant.migration.view"))):
    return success(mig.platform_overview())
