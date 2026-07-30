"""教务文件与数据交换中心（阶段 7）。

本服务把学籍名册导入/导出接入阶段 3 的公共 ImportJob/ExportJob：
- 原始 XLSX 作为不可变 FileObject 留存；
- 预检结果由服务端生成并持久化，确认时重新读取同一 FileObject，不信任前端 rows；
- 确认只接受 jobId + expectedVersion，由公共租约控制多实例幂等；
- 导出生成 FileObject + ExportJob，支持过期、撤销和一次性下载票据。

旧教务接口在阶段 10 调用扫描完成前保留为兼容入口，但新页面只允许调用本服务对应路由。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.services import data_exchange_job_service as jobs

ACADEMIC_MODULE_CODE = "ACADEMIC_AFFAIRS"
ACADEMIC_ROSTER_IMPORT = "ACADEMIC_ROSTER"
ACADEMIC_ROSTER_EXPORT = "ACADEMIC_ROSTER"
_MAX_ROSTER_IMPORT_BYTES = 20 * 1024 * 1024


def _json_safe(value: Any) -> Any:
    """只保存预检摘要；敏感原始行始终留在受控 XLSX，不复制进任务 JSON。"""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _error_items(preview: dict) -> list[dict]:
    raw = preview.get("errors") or preview.get("errorList") or []
    if isinstance(raw, dict):
        raw = [
            {"row": key, "message": value}
            for key, value in raw.items()
        ]
    return [item if isinstance(item, dict) else {"message": str(item)} for item in raw]


def _preview_counts(rows: list[dict], preview: dict) -> tuple[int, int, int]:
    total = int(preview.get("totalRows") or len(rows))
    invalid = int(preview.get("invalidRows") or preview.get("errorRows") or 0)
    if not invalid:
        invalid = len({str(item.get("row") or item.get("rowNo") or "") for item in _error_items(preview)})
    valid = int(preview.get("validRows") if preview.get("validRows") is not None else max(0, total - invalid))
    return total, valid, invalid


def create_roster_import_job(
    *,
    content: bytes,
    filename: str,
    source_file_id: int,
    user: dict,
) -> dict:
    """解析并持久化权威预检任务；不保存前端可篡改的 rows 副本。"""
    if not content:
        raise AppException("VALIDATION_ERROR", "导入文件不能为空")
    if len(content) > _MAX_ROSTER_IMPORT_BYTES:
        raise AppException("FILE_TOO_LARGE", "学籍导入文件超过 20MB，请拆分后重试")

    from app.models.data_exchange import ImportJob, ImportRowError
    from app.modules.academic_affairs.services import academic_affairs_service as roster

    rows = roster.roster_import_read(content)
    preview = roster.roster_import_dry_run(rows)
    errors = _error_items(preview)
    total, valid, invalid = _preview_counts(rows, preview)
    adapter_ref = f"AA-ROSTER-{uuid.uuid4().hex}"
    actor_id = jobs._actor_id(user)
    now = jobs._now()

    db = get_sessionmaker()()
    try:
        row = ImportJob(
            tenant_id=jobs._tenant_id(),
            module_code=ACADEMIC_MODULE_CODE,
            import_type=ACADEMIC_ROSTER_IMPORT,
            source_file_id=int(source_file_id),
            adapter_type=jobs.IMPORT_ADAPTER_EXCEL,
            adapter_ref=adapter_ref,
            template_version="v1",
            status="VALIDATED" if invalid == 0 else "VALIDATION_FAILED",
            total_rows=total,
            valid_rows=valid,
            invalid_rows=invalid,
            operator_id=actor_id,
            operator_name=jobs._actor_name(user),
            expires_at=now + timedelta(hours=jobs.IMPORT_JOB_TTL_HOURS),
            source_snapshot_json={
                "authority": "SOURCE_FILE_OBJECT",
                "fileName": filename,
                "fileSha256": hashlib.sha256(content).hexdigest(),
                "rowDigest": hashlib.sha256(
                    json.dumps(_json_safe(rows), ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "spec": "academicAffairs.roster.v1",
                "preview": {
                    "totalRows": total,
                    "validRows": valid,
                    "invalidRows": invalid,
                },
            },
            created_by=actor_id,
        )
        db.add(row)
        db.flush()
        for item in errors:
            raw = dict(item.get("raw") or item.get("rowData") or {})
            # 身份证号等强敏感原值不进入错误表；原件仍在受控 FileObject。
            raw.pop("idCard", None)
            db.add(ImportRowError(
                tenant_id=jobs._tenant_id(),
                import_job_id=row.id,
                sheet_name=str(item.get("sheetName") or "导入模板")[:100],
                row_no=int(item.get("row") or item.get("rowNo") or 0) or None,
                field_code=str(item.get("field") or item.get("fieldCode") or "")[:100] or None,
                error_code=str(item.get("code") or item.get("errorCode") or "VALIDATION_ERROR")[:80],
                error_message=str(item.get("message") or item.get("reason") or "预检失败")[:1000],
                raw_snapshot_json=_json_safe(raw) if raw else None,
                created_by=actor_id,
            ))
        db.commit()
        db.refresh(row)
        result = jobs._import_row(row)
        result["preview"] = {
            "totalRows": total,
            "validRows": valid,
            "invalidRows": invalid,
            "errors": errors,
        }
        return result
    finally:
        db.close()


def _source_file_bytes(import_row, user: dict) -> bytes:
    from app.models.file import FileObject
    from app.services.file_scan_service import assert_file_ready_for_business
    from app.services.storage import get_backend

    if not import_row.source_file_id:
        raise AppException("DATA_CONFLICT", "导入任务缺少原始文件，请重新上传")
    assert_file_ready_for_business(str(import_row.source_file_id), user=user)
    db = get_sessionmaker()()
    try:
        file_row = db.scalars(select(FileObject).where(
            FileObject.id == int(import_row.source_file_id),
            FileObject.tenant_id == jobs._tenant_id(),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_row:
            raise not_found("导入原始文件不存在")
        path = get_backend().fetch_local(file_row.file_key)
        if not path or not path.exists():
            raise not_found("导入原始文件不存在或已清理")
        if int(file_row.size_bytes or 0) > _MAX_ROSTER_IMPORT_BYTES:
            raise AppException("FILE_TOO_LARGE", "学籍导入文件超过 20MB，请拆分后重试")
        with path.open("rb") as handle:
            return handle.read(_MAX_ROSTER_IMPORT_BYTES + 1)
    finally:
        db.close()


def confirm_roster_import(job_id: str, *, lease: str, user: dict) -> dict:
    """从同一不可变 FileObject 重新解析并确认，前端没有 rows 写入口。"""
    from app.modules.academic_affairs.services import academic_affairs_service as roster

    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user)
        if row.adapter_type != jobs.IMPORT_ADAPTER_EXCEL or row.import_type != ACADEMIC_ROSTER_IMPORT:
            raise AppException("DATA_CONFLICT", "该任务不是教务学籍导入")
        if row.lease_token != lease:
            raise AppException("DATA_CONFLICT", "导入任务确认租约已失效")
        snapshot = dict(row.source_snapshot_json or {})
        content = _source_file_bytes(row, user)
    finally:
        db.close()

    rows = roster.roster_import_read(content)
    digest = hashlib.sha256(json.dumps(_json_safe(rows), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if snapshot.get("rowDigest") and snapshot["rowDigest"] != digest:
        raise AppException("DATA_CONFLICT", "导入文件解析结果已变化，请重新上传预检")
    preview = roster.roster_import_dry_run(rows)
    _total, _valid, invalid = _preview_counts(rows, preview)
    if invalid:
        raise AppException("VALIDATION_ERROR", "确认前重新预检发现错误，请重新上传修正后的文件")
    return roster.roster_import_confirm(rows)


def create_roster_export_job(
    *,
    user: dict,
    purpose: str,
    keyword: str | None = None,
    status: str | None = None,
) -> dict:
    """生成可追踪、可过期、可撤销的学籍名册导出任务。"""
    from app.models.data_exchange import ExportJob
    from app.modules.academic_affairs.services import academic_affairs_service as roster

    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 个字")
    content = roster.export_roster_xlsx(user, purpose, keyword, status)
    _rows, total = roster.roster(user, keyword, status, page=1, page_size=1)
    adapter_ref = f"AA-ROSTER-EXPORT-{uuid.uuid4().hex}"
    file_id = jobs._write_generated_file(
        content,
        "roster_ledger.xlsx",
        biz_id=adapter_ref,
        user=user,
        security_level="SENSITIVE",
    )
    actor_id = jobs._actor_id(user)
    db = get_sessionmaker()()
    try:
        row = ExportJob(
            tenant_id=jobs._tenant_id(),
            module_code=ACADEMIC_MODULE_CODE,
            export_type=ACADEMIC_ROSTER_EXPORT,
            purpose=purpose,
            adapter_type="ACADEMIC_EXPORT",
            adapter_ref=adapter_ref,
            filter_snapshot_json={"keyword": keyword or "", "status": status or ""},
            data_scope_snapshot_json={
                "actorUserId": str(user.get("userId") or ""),
                "roleCode": str(user.get("currentRoleCode") or ""),
            },
            status="SUCCEEDED",
            progress=100,
            row_count=int(total or 0),
            file_object_id=file_id,
            expires_at=jobs._now() + timedelta(hours=jobs.RECEIPT_TTL_HOURS),
            operator_id=actor_id,
            created_by=actor_id,
            finished_at=jobs._now(),
            result_json={"fileObjectId": str(file_id)},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jobs._export_row(row)
    finally:
        db.close()


def list_academic_jobs(*, user: dict, job_type: str = "", status: str = "", page: int = 1, page_size: int = 20) -> dict:
    """只列当前操作者的教务任务，避免系统任务与其它模块混入。"""
    from app.models.data_exchange import ExportJob, ImportJob

    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    actor_id = jobs._actor_id(user)
    wanted = str(job_type or "").upper()
    wanted_status = str(status or "").upper()
    items: list[dict] = []
    db = get_sessionmaker()()
    try:
        if wanted in {"", "IMPORT"}:
            stmt = select(ImportJob).where(
                ImportJob.tenant_id == jobs._tenant_id(),
                ImportJob.module_code == ACADEMIC_MODULE_CODE,
                ImportJob.is_deleted.is_(False),
            )
            if actor_id:
                stmt = stmt.where(ImportJob.operator_id == actor_id)
            if wanted_status:
                stmt = stmt.where(ImportJob.status == wanted_status)
            items.extend(jobs._import_row(row) for row in db.scalars(stmt.order_by(ImportJob.id.desc())).all())
        if wanted in {"", "EXPORT"}:
            stmt = select(ExportJob).where(
                ExportJob.tenant_id == jobs._tenant_id(),
                ExportJob.module_code == ACADEMIC_MODULE_CODE,
                ExportJob.is_deleted.is_(False),
            )
            if actor_id:
                stmt = stmt.where(ExportJob.operator_id == actor_id)
            if wanted_status:
                stmt = stmt.where(ExportJob.status == wanted_status)
            items.extend(jobs._export_row(row) for row in db.scalars(stmt.order_by(ExportJob.id.desc())).all())
        items.sort(key=lambda item: (item.get("createdAt") or "", int(item["id"])), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return {"list": items[start:start + page_size], "total": total, "page": page, "pageSize": page_size}
    finally:
        db.close()
