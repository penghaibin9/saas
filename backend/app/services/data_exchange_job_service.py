"""统一导入导出任务中心服务。

SYS-18 的核心约束：
- 前端确认导入只提交 jobId + expectedVersion，禁止回传预检 rows；
- ImportJob / ExportJob / FileObject 继续作为唯一权威底座；
- OWN / MODULE / TENANT 必须显式授权，不再把 operator_id 为空解释成管理员可见；
- 列表、汇总和错误行分页必须在数据库侧完成；
- 取消与重试只开放真实可执行的状态，不制造假按钮。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, false, func, literal, or_, select, union_all

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.db.session import db_enabled, get_sessionmaker
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

IMPORT_JOB_TTL_HOURS = 24
RECEIPT_TTL_HOURS = 24
DOWNLOAD_TICKET_SECONDS = 180
LEASE_STALE_SECONDS = 5 * 60

IMPORT_ADAPTER_IDENTITY = "IDENTITY_IMPORT_BATCH"
IMPORT_ADAPTER_MIGRATION = "LEGACY_MIGRATION_BATCH"
IMPORT_ADAPTER_EXCEL = "EXCEL_IMPORT_JOB"
PENDING_IDENTITY_ADAPTER = "IDENTITY_IMPORT_FILE"

VISIBILITY_OWN = "OWN"
VISIBILITY_MODULE = "MODULE"
VISIBILITY_TENANT = "TENANT"

# RBAC-09 合并前的双权限兼容。新权限是终态；旧权限只用于迁移期识别模块责任。
MODULE_VIEW_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "SYSTEM": (
        "systemAdmin.dataExchange.viewTenant",
        "systemAdmin.user.import",
        "systemAdmin.migration.view",
        "systemAdmin.migration.import",
    ),
    "ACADEMIC_AFFAIRS": (
        "systemAdmin.dataExchange.viewTenant",
        "academicAffairs.roster.import",
        "academicAffairs.grade.import",
        "academicAffairs.schedule.import",
    ),
}
LEGACY_VIEW_PERMISSIONS = (
    "systemAdmin.user.import",
    "systemAdmin.migration.view",
    "systemAdmin.audit.sensitive.view",
    "academicAffairs.roster.import",
    "academicAffairs.grade.import",
    "academicAffairs.schedule.import",
)


def _now() -> datetime:
    return datetime.utcnow()


def _tenant_id() -> int:
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝访问数据交换任务")
    return value


def _actor(user: dict | None = None) -> dict:
    return user or get_current_user_ctx() or {}


def _actor_id(user: dict | None = None) -> int | None:
    return resolve_message_user_id(_actor(user)) or None


def _actor_key(user: dict | None = None) -> str:
    actor = _actor(user)
    return str(actor.get("userId") or actor.get("sub") or actor.get("loginName") or "").strip()


def _actor_name(user: dict | None = None) -> str:
    actor = _actor(user)
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统管理员")


def _require_db() -> None:
    if not db_enabled():
        raise AppException("SERVER_ERROR", "数据交换任务中心必须启用 MySQL")


def _normalize_module_code(value: str | None) -> str:
    return str(value or "").strip().upper()[:64]


def _normalize_visibility(value: str | None) -> str:
    normalized = str(value or VISIBILITY_OWN).strip().upper()
    if normalized not in {VISIBILITY_OWN, VISIBILITY_MODULE, VISIBILITY_TENANT}:
        raise AppException("VALIDATION_ERROR", "visibility 仅支持 OWN、MODULE、TENANT")
    return normalized


def _can_view_own(user: dict) -> bool:
    return has_permission(user, "systemAdmin.dataExchange.viewOwn") or any(
        has_permission(user, code) for code in LEGACY_VIEW_PERMISSIONS
    )


def _can_view_tenant(user: dict) -> bool:
    return has_permission(user, "systemAdmin.dataExchange.viewTenant")


def _can_view_module(user: dict, module_code: str) -> bool:
    code = _normalize_module_code(module_code)
    if not code:
        return False
    if _can_view_tenant(user):
        return True
    return any(has_permission(user, permission) for permission in MODULE_VIEW_PERMISSIONS.get(code, ()))


def visibility_context(user: dict) -> dict[str, Any]:
    modules = sorted(code for code in MODULE_VIEW_PERMISSIONS if _can_view_module(user, code))
    allowed: list[str] = []
    if _can_view_own(user):
        allowed.append(VISIBILITY_OWN)
    if modules:
        allowed.append(VISIBILITY_MODULE)
    if _can_view_tenant(user):
        allowed.append(VISIBILITY_TENANT)
    if not allowed:
        raise no_permission("无权限查看数据交换任务")
    default = VISIBILITY_TENANT if VISIBILITY_TENANT in allowed else (
        VISIBILITY_MODULE if VISIBILITY_MODULE in allowed else VISIBILITY_OWN
    )
    return {
        "allowedVisibilities": allowed,
        "allowedModules": modules,
        "defaultVisibility": default,
    }


def _resolve_visibility_request(
    user: dict,
    visibility: str | None,
    module_code: str | None,
) -> tuple[str, str]:
    context = visibility_context(user)
    normalized = _normalize_visibility(visibility)
    if normalized not in context["allowedVisibilities"]:
        raise no_permission(f"无权限使用 {normalized} 数据交换视图")
    module = _normalize_module_code(module_code)
    if normalized == VISIBILITY_MODULE:
        allowed_modules = list(context["allowedModules"])
        if not module and len(allowed_modules) == 1:
            module = allowed_modules[0]
        if not module:
            raise AppException("VALIDATION_ERROR", "MODULE 视图必须指定 moduleCode")
        if module not in allowed_modules:
            raise no_permission("无权查看该模块的数据交换任务")
    return normalized, module


def _owner_condition(model, actor_id: int | None):
    if not actor_id:
        return false()
    # 兼容少量旧任务：operator_id 为空时只允许 created_by 为当前人的任务，绝不默认管理员可见。
    return or_(
        model.operator_id == actor_id,
        and_(model.operator_id.is_(None), model.created_by == actor_id),
    )


def _apply_visibility(stmt, model, user: dict, visibility: str, module_code: str):
    if visibility == VISIBILITY_TENANT:
        return stmt
    if visibility == VISIBILITY_MODULE:
        return stmt.where(model.module_code == module_code)
    return stmt.where(_owner_condition(model, _actor_id(user)))


def _row_is_owned(row, user: dict) -> bool:
    actor_id = _actor_id(user)
    if not actor_id:
        return False
    return int(row.operator_id or 0) == actor_id or (
        row.operator_id is None and int(row.created_by or 0) == actor_id
    )


def _assert_row_visible(
    row,
    user: dict,
    *,
    visibility: str | None = None,
    module_code: str | None = None,
) -> None:
    if visibility is None:
        # by-id 服务调用先以“任务真实所有者”作为最小边界。数据交换 API 自身仍在
        # router 层校验动作权限；毕业设计等领域服务则先完成本域范围校验再调用这里。
        # 这恢复合法的领域导出链，但不会把 operator_id 为空解释成管理员可见。
        if _row_is_owned(row, user):
            return
        if _can_view_tenant(user):
            return
        if _can_view_module(user, str(row.module_code or "")):
            return
        raise not_found("数据交换任务不存在")

    normalized, module = _resolve_visibility_request(user, visibility, module_code)
    if normalized == VISIBILITY_TENANT:
        return
    if normalized == VISIBILITY_MODULE:
        if str(row.module_code or "").upper() == module:
            return
        raise not_found("数据交换任务不存在")
    if not _row_is_owned(row, user):
        raise not_found("数据交换任务不存在")


def _effective_import_status(row) -> str:
    status = str(row.status or "")
    if row.expires_at and row.expires_at <= _now() and status not in {"SUCCEEDED", "CANCELLED", "EXPIRED"}:
        return "EXPIRED"
    return status


def _effective_export_status(row) -> str:
    status = str(row.status or "")
    if row.expires_at and row.expires_at <= _now() and status == "SUCCEEDED":
        return "EXPIRED"
    return status


def _import_row(row) -> dict[str, Any]:
    status = _effective_import_status(row)
    result = dict(row.result_json or {})
    return {
        "id": str(row.id),
        "jobType": "IMPORT",
        "moduleCode": row.module_code,
        "importType": row.import_type,
        "sourceFileId": str(row.source_file_id or ""),
        "adapterType": row.adapter_type,
        "adapterRef": row.adapter_ref,
        "templateVersion": row.template_version,
        "status": status,
        "totalRows": int(row.total_rows or 0),
        "validRows": int(row.valid_rows or 0),
        "invalidRows": int(row.invalid_rows or 0),
        "confirmedRows": int(row.confirmed_rows or 0),
        "errorReceiptFileId": str(row.error_receipt_file_id or ""),
        "credentialReceiptFileId": str(row.credential_receipt_file_id or ""),
        "expiresAt": row.expires_at.isoformat(timespec="seconds") if row.expires_at else None,
        "confirmedAt": row.confirmed_at.isoformat(timespec="seconds") if row.confirmed_at else None,
        "operatorName": row.operator_name or "",
        "result": result,
        "errorMessage": row.error_message or "",
        "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "updatedAt": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
        "cancellable": status in {"SCANNING", "PARSING", "VALIDATED", "VALIDATION_FAILED", "FAILED"},
        "retryable": row.adapter_type == PENDING_IDENTITY_ADAPTER and status in {"VALIDATION_FAILED", "FAILED"},
    }


def _export_row(row) -> dict[str, Any]:
    status = _effective_export_status(row)
    strong_sensitive = str(row.export_type or "") == "INITIAL_CREDENTIAL_RECEIPT"
    downloadable = bool(
        status == "SUCCEEDED"
        and row.file_object_id
        and not row.revoked_at
        and (not row.expires_at or row.expires_at > _now())
    )
    return {
        "id": str(row.id),
        "jobType": "EXPORT",
        "moduleCode": row.module_code,
        "exportType": row.export_type,
        "purpose": row.purpose or "",
        "adapterType": row.adapter_type,
        "adapterRef": row.adapter_ref,
        "status": status,
        "progress": int(row.progress or 0),
        "rowCount": int(row.row_count or 0),
        "fileObjectId": str(row.file_object_id or ""),
        "expiresAt": row.expires_at.isoformat(timespec="seconds") if row.expires_at else None,
        "downloadedCount": int(row.downloaded_count or 0),
        "revokedAt": row.revoked_at.isoformat(timespec="seconds") if row.revoked_at else None,
        "revokeReason": row.revoke_reason or "",
        "errorMessage": row.error_message or "",
        "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "updatedAt": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
        "downloadable": downloadable,
        "strongSensitive": strong_sensitive,
        "oneTimeTicket": True,
        "validityHours": RECEIPT_TTL_HOURS if strong_sensitive else None,
    }


def _owned_import(
    db,
    job_id: str | int,
    user: dict,
    *,
    lock: bool = False,
    visibility: str | None = None,
    module_code: str | None = None,
):
    from app.models.data_exchange import ImportJob

    raw = str(job_id or "").strip()
    if not raw.isdigit():
        raise not_found("导入任务不存在")
    stmt = select(ImportJob).where(
        ImportJob.id == int(raw),
        ImportJob.tenant_id == _tenant_id(),
        ImportJob.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    if not row:
        raise not_found("导入任务不存在")
    _assert_row_visible(row, user, visibility=visibility, module_code=module_code)
    return row


def _owned_export(
    db,
    job_id: str | int,
    user: dict,
    *,
    lock: bool = False,
    visibility: str | None = None,
    module_code: str | None = None,
):
    from app.models.data_exchange import ExportJob

    raw = str(job_id or "").strip()
    if not raw.isdigit():
        raise not_found("导出任务不存在")
    stmt = select(ExportJob).where(
        ExportJob.id == int(raw),
        ExportJob.tenant_id == _tenant_id(),
        ExportJob.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    if not row:
        raise not_found("导出任务不存在")
    _assert_row_visible(row, user, visibility=visibility, module_code=module_code)
    return row


def _write_generated_file(
    content: bytes,
    filename: str,
    *,
    biz_id: str,
    user: dict,
    security_level: str = "SENSITIVE",
) -> int:
    """系统生成 XLSX/PDF/ZIP 直接登记为 CLEAN/AVAILABLE，不经过用户上传扫描链。"""
    from app.core.config import settings
    from app.models.file import FileObject
    from app.services.file_content_security import sanitize_filename
    from app.services.file_scan_constants import SCAN_NOT_REQUIRED

    safe_name = sanitize_filename(filename or "回执.xlsx")
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "bin"
    key = f"exports/{_tenant_id()}/{datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    staged = backend.staging_path(key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(content)
    try:
        backend.persist(key, staged)
    except Exception:
        staged.unlink(missing_ok=True)
        raise

    db = get_sessionmaker()()
    try:
        now = _now()
        row = FileObject(
            tenant_id=_tenant_id(),
            file_key=key,
            file_name=safe_name,
            ext=ext,
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if ext == "xlsx" else "application/octet-stream"
            ),
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            biz_type="DATA_EXCHANGE_RECEIPT",
            biz_id=str(biz_id),
            owner_user_id=_actor_id(user),
            created_by=_actor_id(user),
            visibility="PRIVATE",
            security_level=security_level,
            status="AVAILABLE",
            storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
            storage_zone="EXPORT",
            upload_source="SYSTEM",
            scan_required=False,
            scan_status=SCAN_NOT_REQUIRED,
            scan_attempts=0,
            scanned_at=now,
            available_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    except Exception:
        db.rollback()
        try:
            backend.delete(key)
        except Exception:
            pass
        raise
    finally:
        db.close()


def _create_export_job(
    *,
    export_type: str,
    purpose: str,
    file_object_id: int,
    row_count: int,
    user: dict,
    adapter_type: str | None = None,
    adapter_ref: str | None = None,
    expires_at: datetime | None = None,
) -> dict:
    from app.models.data_exchange import ExportJob

    db = get_sessionmaker()()
    try:
        row = ExportJob(
            tenant_id=_tenant_id(),
            module_code="SYSTEM",
            export_type=export_type,
            purpose=purpose,
            adapter_type=adapter_type,
            adapter_ref=adapter_ref,
            status="SUCCEEDED",
            progress=100,
            row_count=max(0, int(row_count or 0)),
            file_object_id=file_object_id,
            expires_at=expires_at or (_now() + timedelta(hours=RECEIPT_TTL_HOURS)),
            operator_id=_actor_id(user),
            created_by=_actor_id(user),
            finished_at=_now(),
            result_json={"fileObjectId": str(file_object_id)},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _export_row(row)
    finally:
        db.close()


def create_identity_import_job(
    *,
    kind: str,
    source_file_id: str,
    parsed: dict,
    batch_result: dict,
    user: dict,
) -> dict:
    """把现有 IdentityImportBatch 注册为统一 ImportJob。"""
    _require_db()
    from app.models.data_exchange import ImportJob, ImportRowError
    from app.services.identity_import_file_service import build_error_workbook, get_batch

    kind_up = str(kind or "").upper()
    if kind_up not in {"STUDENT", "TEACHER"}:
        raise AppException("VALIDATION_ERROR", "身份导入类型仅支持 STUDENT 或 TEACHER")
    batch_no = str(batch_result.get("batchNo") or "").strip()
    if not batch_no:
        raise AppException("SERVER_ERROR", "身份导入批次创建失败")
    errors = list(batch_result.get("errors") or [])
    relation_errors = list((batch_result.get("relations") or {}).get("errors") or [])
    all_errors = errors + relation_errors
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == _tenant_id(),
            ImportJob.adapter_type == IMPORT_ADAPTER_IDENTITY,
            ImportJob.adapter_ref == batch_no,
            ImportJob.is_deleted.is_(False),
        )).first()
        if existing:
            _assert_row_visible(existing, user)
            return _import_row(existing)
        row = ImportJob(
            tenant_id=_tenant_id(),
            module_code="SYSTEM",
            import_type=f"IDENTITY_{kind_up}",
            source_file_id=int(source_file_id) if str(source_file_id).isdigit() else None,
            adapter_type=IMPORT_ADAPTER_IDENTITY,
            adapter_ref=batch_no,
            template_version="v1",
            status="VALIDATED" if not all_errors else "VALIDATION_FAILED",
            total_rows=int(batch_result.get("total") or parsed.get("totalRows") or 0),
            valid_rows=int(batch_result.get("valid") or 0),
            invalid_rows=int(batch_result.get("invalid") or len(all_errors)),
            operator_id=actor_id,
            operator_name=_actor_name(user),
            expires_at=_now() + timedelta(hours=IMPORT_JOB_TTL_HOURS),
            source_snapshot_json={
                "fileName": parsed.get("fileName"),
                "fileSha256": parsed.get("fileSha256"),
                "kind": kind_up,
                "roleTemplateVersion": batch_result.get("roleTemplateVersion"),
            },
            created_by=actor_id,
        )
        db.add(row)
        db.flush()
        for item in all_errors:
            db.add(ImportRowError(
                tenant_id=_tenant_id(),
                import_job_id=row.id,
                sheet_name="业务关系" if item in relation_errors else "导入模板",
                row_no=int(item.get("row") or 0) or None,
                field_code=str(item.get("field") or "")[:100] or None,
                error_code=str(item.get("errorCode") or "VALIDATION_ERROR")[:80],
                error_message=str(item.get("message") or item.get("error") or "校验失败")[:1000],
                raw_snapshot_json={"entity": item.get("entity"), "row": item.get("row")},
                created_by=actor_id,
            ))
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if all_errors:
        entry = get_batch(user, _tenant_id(), batch_no)
        receipt_bytes = build_error_workbook(entry)
        file_id = _write_generated_file(
            receipt_bytes,
            f"师生账号导入错误_{batch_no}.xlsx",
            biz_id=f"IMPORT:{row.id}:ERRORS",
            user=user,
            security_level="SENSITIVE",
        )
        _create_export_job(
            export_type="IMPORT_ERROR_RECEIPT",
            purpose="导入预检错误回执",
            file_object_id=file_id,
            row_count=len(all_errors),
            user=user,
            adapter_type="IMPORT_JOB",
            adapter_ref=str(row.id),
        )
        db = get_sessionmaker()()
        try:
            current = db.get(ImportJob, row.id)
            current.error_receipt_file_id = file_id
            current.version = int(current.version or 0) + 1
            db.commit()
            db.refresh(current)
            return _import_row(current)
        finally:
            db.close()
    return _import_row(row)


def register_legacy_import_adapter(
    *,
    adapter_type: str,
    adapter_ref: str,
    module_code: str,
    import_type: str,
    source_file_id: int | None,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    status: str,
    snapshot: dict | None,
    user: dict,
) -> dict:
    """迁移/教务 Excel adapter 共用入口；只登记真实后端批次，不接收前端 rows。"""
    _require_db()
    from app.models.data_exchange import ImportJob

    if adapter_type not in {IMPORT_ADAPTER_MIGRATION, IMPORT_ADAPTER_EXCEL}:
        raise AppException("VALIDATION_ERROR", "不支持的导入 adapter")
    ref = str(adapter_ref or "").strip()
    if not ref:
        raise AppException("VALIDATION_ERROR", "adapterRef 不能为空")
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == _tenant_id(),
            ImportJob.adapter_type == adapter_type,
            ImportJob.adapter_ref == ref,
            ImportJob.is_deleted.is_(False),
        )).first()
        if row:
            _assert_row_visible(row, user)
            return _import_row(row)
        row = ImportJob(
            tenant_id=_tenant_id(),
            module_code=str(module_code or "SYSTEM").upper(),
            import_type=str(import_type or adapter_type).upper(),
            source_file_id=source_file_id,
            adapter_type=adapter_type,
            adapter_ref=ref,
            status=str(status or "VALIDATED").upper(),
            total_rows=max(0, int(total_rows or 0)),
            valid_rows=max(0, int(valid_rows or 0)),
            invalid_rows=max(0, int(invalid_rows or 0)),
            operator_id=_actor_id(user),
            operator_name=_actor_name(user),
            expires_at=_now() + timedelta(hours=IMPORT_JOB_TTL_HOURS),
            source_snapshot_json=snapshot or {},
            created_by=_actor_id(user),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _import_row(row)
    finally:
        db.close()


def confirm_identity_import_job(
    job_id: str,
    *,
    expected_version: int,
    user: dict,
    idempotency_key: str | None = None,
) -> dict:
    """确认身份导入；权威输入只有 jobId/expectedVersion/Idempotency-Key。"""
    _require_db()
    from app.models.data_exchange import ImportJob
    from app.services.file_scan_service import assert_file_ready_for_business
    from app.services.identity_import_file_service import (
        build_credential_receipt,
        claim_batch,
        mark_confirmed,
        release_claim,
    )
    from app.services.identity_import_service import run_identity_import

    if idempotency_key is not None and len(str(idempotency_key).strip()) < 16:
        raise AppException("VALIDATION_ERROR", "Idempotency-Key 长度不能少于 16 个字符")
    lease = secrets.token_hex(32)
    batch_claim: str | None = None
    batch_entry: dict | None = None
    db = get_sessionmaker()()
    try:
        row = _owned_import(db, job_id, user, lock=True)
        if row.adapter_type != IMPORT_ADAPTER_IDENTITY:
            raise AppException("DATA_CONFLICT", "该任务不是身份账号导入，不能使用此确认接口")
        if row.status == "SUCCEEDED":
            return _import_row(row)
        if row.expires_at and row.expires_at <= _now():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            raise AppException("DATA_CONFLICT", "导入任务已过期，请重新上传预检")
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        if row.invalid_rows or row.status == "VALIDATION_FAILED":
            raise AppException("VALIDATION_ERROR", "该任务存在预检错误，禁止确认导入")
        if row.status == "CONFIRMING" and row.lease_started_at \
                and row.lease_started_at > _now() - timedelta(seconds=LEASE_STALE_SECONDS):
            raise AppException("DATA_CONFLICT", "该任务正在另一服务实例确认，请稍后刷新")
        if row.status not in {"VALIDATED", "CONFIRMING", "FAILED"}:
            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许确认")
        row.status = "CONFIRMING"
        row.lease_token = lease
        row.lease_started_at = _now()
        row.error_message = None
        snapshot = dict(row.source_snapshot_json or {})
        if idempotency_key:
            snapshot["confirmIdempotencyHash"] = hashlib.sha256(
                str(idempotency_key).encode("utf-8")
            ).hexdigest()
        row.source_snapshot_json = snapshot
        row.version = int(row.version or 0) + 1
        source_file_id = str(row.source_file_id or "")
        batch_no = row.adapter_ref
        db.commit()
    finally:
        db.close()

    try:
        if not source_file_id:
            raise AppException("DATA_CONFLICT", "导入任务缺少原始文件，请重新上传")
        assert_file_ready_for_business(source_file_id, user=user)
        batch_entry, batch_claim, already_confirmed = claim_batch(user, _tenant_id(), batch_no)
        if already_confirmed:
            public_result = dict(batch_entry.get("publicResult") or {})
            credential = None
        else:
            report = run_identity_import(user, batch_entry["payload"], dry_run=False)
            credential = build_credential_receipt(batch_entry, report)
            public_result = {
                key: value for key, value in report.items()
                if key not in {"studentCredentials", "teacherCredentials"}
            }
            mark_confirmed(user, _tenant_id(), batch_no, batch_claim, public_result)

        credential_file_id = None
        credential_export_job = None
        if credential:
            content = base64.b64decode(credential["contentBase64"])
            credential_file_id = _write_generated_file(
                content,
                credential["filename"],
                biz_id=f"IMPORT:{job_id}:CREDENTIALS",
                user=user,
                security_level="HIGHLY_SENSITIVE",
            )
            credential_export_job = _create_export_job(
                export_type="INITIAL_CREDENTIAL_RECEIPT",
                purpose="初始账号凭据一次性安全回执",
                file_object_id=credential_file_id,
                row_count=int(credential.get("rowCount") or 0),
                user=user,
                adapter_type="IMPORT_JOB",
                adapter_ref=str(job_id),
                expires_at=_now() + timedelta(hours=RECEIPT_TTL_HOURS),
            )

        db = get_sessionmaker()()
        try:
            row = _owned_import(db, job_id, user, lock=True)
            if row.lease_token != lease and row.status != "SUCCEEDED":
                raise AppException("DATA_CONFLICT", "导入任务确认租约已失效")
            row.status = "SUCCEEDED"
            row.confirmed_rows = int(
                public_result.get("createdCount")
                or public_result.get("insertedRows")
                or row.valid_rows
                or 0
            )
            row.confirmed_at = _now()
            row.credential_receipt_file_id = credential_file_id
            row.result_json = {
                **public_result,
                "credentialReceiptFileId": str(credential_file_id or ""),
                "credentialExportJobId": str((credential_export_job or {}).get("id") or ""),
            }
            row.lease_token = None
            row.lease_started_at = None
            row.error_message = None
            row.version = int(row.version or 0) + 1
            db.commit()
            db.refresh(row)
            return _import_row(row)
        finally:
            db.close()
    except Exception as exc:
        if batch_claim and batch_entry:
            try:
                release_claim(user, _tenant_id(), batch_no, batch_claim, str(exc))
            except Exception:
                pass
        db = get_sessionmaker()()
        try:
            row = _owned_import(db, job_id, user, lock=True)
            if row.lease_token == lease:
                row.status = "VALIDATED"
                row.lease_token = None
                row.lease_started_at = None
                row.error_message = str(exc)[:4000]
                row.version = int(row.version or 0) + 1
                db.commit()
        finally:
            db.close()
        raise


def _status_condition(model, wanted_status: str, *, export: bool):
    wanted = str(wanted_status or "").upper()
    if not wanted:
        return None
    if wanted == "EXPIRED":
        if export:
            return or_(
                model.status == "EXPIRED",
                and_(model.status == "SUCCEEDED", model.expires_at.is_not(None), model.expires_at <= _now()),
            )
        return or_(
            model.status == "EXPIRED",
            and_(
                model.status.notin_(["SUCCEEDED", "CANCELLED"]),
                model.expires_at.is_not(None),
                model.expires_at <= _now(),
            ),
        )
    return model.status == wanted


def list_jobs(
    *,
    user: dict,
    job_type: str = "",
    status: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    visibility: str = VISIBILITY_OWN,
    module_code: str = "",
) -> dict:
    """数据库侧稳定归并分页；最多只加载当前页任务实体。"""
    _require_db()
    from app.models.data_exchange import ExportJob, ImportJob

    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    wanted = str(job_type or "").upper()
    if wanted not in {"", "IMPORT", "EXPORT"}:
        raise AppException("VALIDATION_ERROR", "jobType 仅支持 IMPORT 或 EXPORT")
    keyword = str(keyword or "").strip()
    visibility, module_code = _resolve_visibility_request(user, visibility, module_code)
    db = get_sessionmaker()()
    try:
        parts = []
        if wanted in {"", "IMPORT"}:
            stmt = select(
                literal("IMPORT").label("job_type"),
                ImportJob.id.label("job_id"),
                ImportJob.created_at.label("created_at"),
            ).where(
                ImportJob.tenant_id == _tenant_id(),
                ImportJob.is_deleted.is_(False),
            )
            stmt = _apply_visibility(stmt, ImportJob, user, visibility, module_code)
            condition = _status_condition(ImportJob, status, export=False)
            if condition is not None:
                stmt = stmt.where(condition)
            if keyword:
                like = f"%{keyword}%"
                stmt = stmt.where(or_(
                    ImportJob.import_type.like(like),
                    ImportJob.adapter_ref.like(like),
                    ImportJob.module_code.like(like),
                    ImportJob.operator_name.like(like),
                ))
            parts.append(stmt)
        if wanted in {"", "EXPORT"}:
            stmt = select(
                literal("EXPORT").label("job_type"),
                ExportJob.id.label("job_id"),
                ExportJob.created_at.label("created_at"),
            ).where(
                ExportJob.tenant_id == _tenant_id(),
                ExportJob.is_deleted.is_(False),
            )
            stmt = _apply_visibility(stmt, ExportJob, user, visibility, module_code)
            condition = _status_condition(ExportJob, status, export=True)
            if condition is not None:
                stmt = stmt.where(condition)
            if keyword:
                like = f"%{keyword}%"
                stmt = stmt.where(or_(
                    ExportJob.export_type.like(like),
                    ExportJob.purpose.like(like),
                    ExportJob.module_code.like(like),
                ))
            parts.append(stmt)

        combined = parts[0].subquery() if len(parts) == 1 else union_all(*parts).subquery()
        total = int(db.scalar(select(func.count()).select_from(combined)) or 0)
        refs = db.execute(
            select(combined.c.job_type, combined.c.job_id, combined.c.created_at)
            .order_by(combined.c.created_at.desc(), combined.c.job_id.desc(), combined.c.job_type.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        import_ids = [int(ref.job_id) for ref in refs if ref.job_type == "IMPORT"]
        export_ids = [int(ref.job_id) for ref in refs if ref.job_type == "EXPORT"]
        imports = {}
        exports = {}
        if import_ids:
            imports = {
                int(row.id): row for row in db.scalars(select(ImportJob).where(
                    ImportJob.tenant_id == _tenant_id(),
                    ImportJob.id.in_(import_ids),
                    ImportJob.is_deleted.is_(False),
                )).all()
            }
        if export_ids:
            exports = {
                int(row.id): row for row in db.scalars(select(ExportJob).where(
                    ExportJob.tenant_id == _tenant_id(),
                    ExportJob.id.in_(export_ids),
                    ExportJob.is_deleted.is_(False),
                )).all()
            }
        rows: list[dict] = []
        for ref in refs:
            if ref.job_type == "IMPORT" and int(ref.job_id) in imports:
                rows.append(_import_row(imports[int(ref.job_id)]))
            elif ref.job_type == "EXPORT" and int(ref.job_id) in exports:
                rows.append(_export_row(exports[int(ref.job_id)]))
        return {
            "list": rows,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "visibility": visibility,
            "moduleCode": module_code or None,
            **visibility_context(user),
        }
    finally:
        db.close()


def _aggregate_query(model, user: dict, visibility: str, module_code: str, columns):
    stmt = select(*columns).where(
        model.tenant_id == _tenant_id(),
        model.is_deleted.is_(False),
    )
    return _apply_visibility(stmt, model, user, visibility, module_code)


def get_summary(
    *,
    user: dict,
    visibility: str = VISIBILITY_OWN,
    module_code: str = "",
) -> dict:
    """独立 aggregate API；结果不受当前页、关键词或列表 pageSize 影响。"""
    _require_db()
    from app.models.data_exchange import ExportJob, ImportJob

    visibility, module_code = _resolve_visibility_request(user, visibility, module_code)
    now = _now()
    import_expired = or_(
        ImportJob.status == "EXPIRED",
        and_(
            ImportJob.status.notin_(["SUCCEEDED", "CANCELLED"]),
            ImportJob.expires_at.is_not(None),
            ImportJob.expires_at <= now,
        ),
    )
    export_expired = or_(
        ExportJob.status == "EXPIRED",
        and_(ExportJob.status == "SUCCEEDED", ExportJob.expires_at.is_not(None), ExportJob.expires_at <= now),
    )
    db = get_sessionmaker()()
    try:
        import_row = db.execute(_aggregate_query(
            ImportJob,
            user,
            visibility,
            module_code,
            (
                func.count(ImportJob.id),
                func.sum(case((ImportJob.status.in_(["VALIDATED", "CONFIRMING"]), 1), else_=0)),
                func.sum(case((ImportJob.status.in_(["SCANNING", "PARSING"]), 1), else_=0)),
                func.sum(case((ImportJob.status.in_(["VALIDATION_FAILED", "FAILED"]), 1), else_=0)),
                func.sum(case((import_expired, 1), else_=0)),
            ),
        )).one()
        export_row = db.execute(_aggregate_query(
            ExportJob,
            user,
            visibility,
            module_code,
            (
                func.count(ExportJob.id),
                func.sum(case((ExportJob.status.in_(["CREATED", "RUNNING"]), 1), else_=0)),
                func.sum(case((ExportJob.status == "FAILED", 1), else_=0)),
                func.sum(case((export_expired, 1), else_=0)),
                func.sum(case((and_(
                    ExportJob.status == "SUCCEEDED",
                    ExportJob.file_object_id.is_not(None),
                    ExportJob.revoked_at.is_(None),
                    or_(ExportJob.expires_at.is_(None), ExportJob.expires_at > now),
                ), 1), else_=0)),
            ),
        )).one()
        import_total = int(import_row[0] or 0)
        export_total = int(export_row[0] or 0)
        return {
            "total": import_total + export_total,
            "imports": import_total,
            "exports": export_total,
            "pending": int(import_row[1] or 0) + int(export_row[1] or 0),
            "scanning": int(import_row[2] or 0),
            "failed": int(import_row[3] or 0) + int(export_row[2] or 0),
            "expired": int(import_row[4] or 0) + int(export_row[3] or 0),
            "receipts": int(export_row[4] or 0),
            "visibility": visibility,
            "moduleCode": module_code or None,
            "generatedAt": now.isoformat(timespec="seconds"),
            **visibility_context(user),
        }
    finally:
        db.close()


def _source_file_projection(db, row) -> dict | None:
    if not row.source_file_id:
        return None
    from app.models.file import FileObject

    file_row = db.scalars(select(FileObject).where(
        FileObject.id == int(row.source_file_id),
        FileObject.tenant_id == _tenant_id(),
        FileObject.is_deleted.is_(False),
    )).first()
    if not file_row:
        return {"id": str(row.source_file_id), "status": "MISSING", "scanStatus": "UNKNOWN"}
    return {
        "id": str(file_row.id),
        "fileName": file_row.file_name or "",
        "status": file_row.status,
        "scanStatus": file_row.scan_status,
        "securityLevel": file_row.security_level,
        "sizeBytes": int(file_row.size_bytes or 0),
        "availableAt": file_row.available_at.isoformat(timespec="seconds") if file_row.available_at else None,
    }


def get_import_job(
    job_id: str,
    *,
    user: dict,
    visibility: str | None = None,
    module_code: str | None = None,
) -> dict:
    from app.models.data_exchange import ImportRowError

    db = get_sessionmaker()()
    try:
        row = _owned_import(
            db, job_id, user, visibility=visibility, module_code=module_code
        )
        data = _import_row(row)
        error_count = int(db.scalar(select(func.count()).select_from(ImportRowError).where(
            ImportRowError.tenant_id == _tenant_id(),
            ImportRowError.import_job_id == row.id,
            ImportRowError.is_deleted.is_(False),
        )) or 0)
        result = dict(row.result_json or {})
        timeline = [
            {"event": "CREATED", "at": data["createdAt"]},
        ]
        if result.get("parseStartedAt"):
            timeline.append({"event": "PARSING_STARTED", "at": result.get("parseStartedAt")})
        if result.get("parseFinishedAt"):
            timeline.append({"event": "PARSING_FINISHED", "at": result.get("parseFinishedAt")})
        if data["confirmedAt"]:
            timeline.append({"event": "CONFIRMED", "at": data["confirmedAt"]})
        data.update({
            "sourceFile": _source_file_projection(db, row),
            "errorCount": error_count,
            "adapter": {
                "type": row.adapter_type,
                "ref": row.adapter_ref,
                "moduleCode": row.module_code,
            },
            "timeline": timeline,
        })
        return data
    finally:
        db.close()


def get_import_errors(
    job_id: str,
    *,
    user: dict,
    page: int = 1,
    page_size: int = 50,
    visibility: str | None = None,
    module_code: str | None = None,
) -> dict:
    from app.models.data_exchange import ImportRowError

    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    db = get_sessionmaker()()
    try:
        row = _owned_import(
            db, job_id, user, visibility=visibility, module_code=module_code
        )
        base = select(ImportRowError).where(
            ImportRowError.tenant_id == _tenant_id(),
            ImportRowError.import_job_id == row.id,
            ImportRowError.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        errors = db.scalars(
            base.order_by(ImportRowError.row_no.asc(), ImportRowError.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "list": [
                {
                    "id": str(item.id),
                    "sheetName": item.sheet_name or "",
                    "rowNo": item.row_no,
                    "fieldCode": item.field_code or "",
                    "errorCode": item.error_code or "",
                    "message": item.error_message,
                    "snapshot": item.raw_snapshot_json or {},
                }
                for item in errors
            ],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    finally:
        db.close()


def get_export_job(
    job_id: str,
    *,
    user: dict,
    visibility: str | None = None,
    module_code: str | None = None,
) -> dict:
    db = get_sessionmaker()()
    try:
        row = _owned_export(
            db, job_id, user, visibility=visibility, module_code=module_code
        )
        data = _export_row(row)
        data["timeline"] = [
            {"event": "CREATED", "at": data["createdAt"]},
            {"event": "FINISHED", "at": row.finished_at.isoformat(timespec="seconds") if row.finished_at else None},
            {"event": "REVOKED", "at": data["revokedAt"]} if data["revokedAt"] else None,
        ]
        data["timeline"] = [item for item in data["timeline"] if item and item.get("at")]
        return data
    finally:
        db.close()


def _audit_action(action: str, target: str, *, detail: dict) -> None:
    try:
        from app.services import audit_log

        audit_log.record(action, target, detail=detail, result="SUCCESS")
    except Exception:
        pass


def cancel_import_job(
    job_id: str,
    *,
    expected_version: int,
    reason: str,
    user: dict,
) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因必填且不少于 5 个字")
    db = get_sessionmaker()()
    try:
        row = _owned_import(db, job_id, user, lock=True)
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        if row.status == "CANCELLED":
            return _import_row(row)
        if row.status in {"SUCCEEDED", "EXPIRED"}:
            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许取消")
        if row.status == "CONFIRMING" and row.lease_started_at \
                and row.lease_started_at > _now() - timedelta(seconds=LEASE_STALE_SECONDS):
            raise AppException("DATA_CONFLICT", "任务正在确认写入，不能取消")
        if row.status not in {"SCANNING", "PARSING", "VALIDATED", "VALIDATION_FAILED", "FAILED", "CONFIRMING"}:
            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许取消")
        result = dict(row.result_json or {})
        result["cancellation"] = {
            "reason": reason[:500],
            "cancelledAt": _now().isoformat(timespec="seconds"),
            "cancelledBy": _actor_key(user),
        }
        row.result_json = result
        row.status = "CANCELLED"
        row.lease_token = None
        row.lease_started_at = None
        row.error_message = reason[:4000]
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        data = _import_row(row)
    finally:
        db.close()
    _audit_action("DATA_EXCHANGE_IMPORT_CANCEL", f"import-job:{job_id}", detail={"reason": reason})
    return data


def retry_import_job(
    job_id: str,
    *,
    expected_version: int,
    user: dict,
) -> dict:
    """真实重投身份文件扫描队列；业务预检错误和外部 adapter 不制造假重试。"""
    from app.models.file import FileObject
    from app.services.file_scan_constants import SCAN_INFECTED
    from app.services.file_scan_service import enqueue_file_scan

    db = get_sessionmaker()()
    try:
        row = _owned_import(db, job_id, user, lock=True)
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        if row.expires_at and row.expires_at <= _now():
            raise AppException("DATA_CONFLICT", "任务已过期，请重新上传文件")
        if row.adapter_type != PENDING_IDENTITY_ADAPTER:
            raise AppException("DATA_CONFLICT", "该任务必须回对应业务入口修正，不能在任务中心假重试")
        if row.status not in {"VALIDATION_FAILED", "FAILED"}:
            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许重试")
        if not row.source_file_id:
            raise AppException("DATA_CONFLICT", "任务缺少原始文件，不能重试")
        file_row = db.scalars(select(FileObject).where(
            FileObject.id == int(row.source_file_id),
            FileObject.tenant_id == _tenant_id(),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_row:
            raise not_found("导入源文件不存在")
        if str(file_row.scan_status or "").upper() == SCAN_INFECTED \
                or str(file_row.status or "").upper() == "REJECTED":
            raise AppException("FILE_REJECTED", "感染文件不可重试或人工放行")

        enqueue_file_scan(db, file_row)
        result = dict(row.result_json or {})
        result["parseStartedAt"] = None
        result["retryCount"] = int(result.get("retryCount") or 0) + 1
        result["lastRetryAt"] = _now().isoformat(timespec="seconds")
        result["scanRequeued"] = True
        row.result_json = result
        row.status = "SCANNING"
        row.error_message = None
        row.lease_token = None
        row.lease_started_at = None
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        data = _import_row(row)
    finally:
        db.close()
    _audit_action("DATA_EXCHANGE_IMPORT_RETRY", f"import-job:{job_id}", detail={"version": data["version"]})
    return data


def create_download_ticket(job_id: str, *, expected_version: int, user: dict) -> dict:
    """为已完成且未过期/未撤销的导出创建短时一次性票据。"""
    raw_token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = _now() + timedelta(seconds=DOWNLOAD_TICKET_SECONDS)
    db = get_sessionmaker()()
    try:
        row = _owned_export(db, job_id, user, lock=True)
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "导出任务版本已变化，请刷新后重试")
        if row.revoked_at or row.status == "REVOKED":
            raise not_found("导出任务不存在或已撤销")
        if row.expires_at and row.expires_at <= _now():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            raise not_found("导出文件已过期")
        if row.status != "SUCCEEDED" or not row.file_object_id:
            raise AppException("DATA_CONFLICT", "导出文件尚未生成完成")
        result = dict(row.result_json or {})
        result["downloadTicket"] = {
            "sha256": token_hash,
            "expiresAt": expires_at.isoformat(timespec="seconds"),
            "used": False,
        }
        row.result_json = result
        row.version = int(row.version or 0) + 1
        db.commit()
        return {
            "ticket": raw_token,
            "expiresAt": expires_at.isoformat(timespec="seconds"),
            "downloadUrl": f"/api/v1/data-exchange/exports/{row.id}/download?ticket={raw_token}",
            "version": int(row.version or 0),
        }
    finally:
        db.close()


def consume_download_ticket(job_id: str, ticket: str, *, user: dict) -> tuple[Path, str]:
    from app.models.file import FileObject

    token_hash = hashlib.sha256(str(ticket or "").encode("utf-8")).hexdigest()
    db = get_sessionmaker()()
    try:
        row = _owned_export(db, job_id, user, lock=True)
        if row.revoked_at or row.status in {"REVOKED", "EXPIRED"}:
            raise not_found("导出任务不存在或已失效")
        if row.expires_at and row.expires_at <= _now():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            raise not_found("导出文件已过期")
        token_data = dict((row.result_json or {}).get("downloadTicket") or {})
        try:
            ticket_expires = datetime.fromisoformat(str(token_data.get("expiresAt") or ""))
        except ValueError:
            ticket_expires = datetime.min
        if (
            not token_data
            or token_data.get("used")
            or token_data.get("sha256") != token_hash
            or ticket_expires <= _now()
        ):
            raise not_found("下载票据不存在或已失效")
        file_row = db.scalars(select(FileObject).where(
            FileObject.id == row.file_object_id,
            FileObject.tenant_id == _tenant_id(),
            FileObject.is_deleted.is_(False),
            FileObject.status == "AVAILABLE",
        )).first()
        if not file_row:
            raise not_found("导出文件不存在或已清理")
        path = get_backend().fetch_local(file_row.file_key)
        if not path or not path.exists():
            raise not_found("导出文件不存在或已清理")
        result = dict(row.result_json or {})
        token_data["used"] = True
        token_data["usedAt"] = _now().isoformat(timespec="seconds")
        result["downloadTicket"] = token_data
        row.result_json = result
        row.downloaded_count = int(row.downloaded_count or 0) + 1
        row.version = int(row.version or 0) + 1
        filename = file_row.file_name or path.name
        db.commit()
        return path, filename
    finally:
        db.close()


def revoke_export_job(job_id: str, *, expected_version: int, reason: str, user: dict) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "撤销原因必填且不少于 5 个字")
    db = get_sessionmaker()()
    try:
        row = _owned_export(db, job_id, user, lock=True)
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "导出任务版本已变化，请刷新后重试")
        if row.revoked_at:
            return _export_row(row)
        row.status = "REVOKED"
        row.revoked_at = _now()
        row.revoke_reason = reason[:500]
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _export_row(row)
    finally:
        db.close()


def cleanup_expired_jobs(*, limit: int = 200) -> dict:
    """定时任务入口：标记过期并删除可重建的导出字节，保留审计元数据。"""
    from app.models.data_exchange import ExportJob, ImportJob
    from app.models.file import FileObject

    now = _now()
    db = get_sessionmaker()()
    import_count = export_count = file_count = 0
    try:
        imports = db.scalars(select(ImportJob).where(
            ImportJob.is_deleted.is_(False),
            ImportJob.expires_at.is_not(None),
            ImportJob.expires_at <= now,
            ImportJob.status.notin_(["SUCCEEDED", "EXPIRED"]),
        ).limit(limit)).all()
        for row in imports:
            row.status = "EXPIRED"
            row.lease_token = None
            row.lease_started_at = None
            row.version = int(row.version or 0) + 1
            import_count += 1
        exports = db.scalars(select(ExportJob).where(
            ExportJob.is_deleted.is_(False),
            ExportJob.expires_at.is_not(None),
            ExportJob.expires_at <= now,
            ExportJob.status == "SUCCEEDED",
        ).limit(limit)).all()
        for row in exports:
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            if row.file_object_id:
                file_row = db.get(FileObject, row.file_object_id)
                if file_row and not file_row.is_deleted:
                    try:
                        get_backend().delete(file_row.file_key)
                    except Exception:
                        continue
                    file_row.is_deleted = True
                    file_row.status = "DELETED"
                    file_row.version = int(file_row.version or 0) + 1
                    file_count += 1
            export_count += 1
        db.commit()
        return {"expiredImports": import_count, "expiredExports": export_count, "deletedFiles": file_count}
    finally:
        db.close()
