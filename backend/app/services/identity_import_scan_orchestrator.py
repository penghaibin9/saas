"""身份导入 FileObject 扫描后 I3 staging 编排。

上传请求只登记隔离文件和 ImportJob；文件 CLEAN/AVAILABLE 后由任务创建者或
canonical identity-import worker 显式推进 PARSING → normalized staging → preview。
详情读取本身不替他人执行解析。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob
from app.models.file import FileObject
from app.services import data_exchange_job_service as jobs
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES
from app.services.storage import get_backend

PARSING_STALE_SECONDS = 5 * 60
PENDING_ADAPTER = "IDENTITY_IMPORT_FILE"
WORKER_CLAIMED = "WORKER_CLAIMED"


def _kind(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized not in {"STUDENT", "TEACHER"}:
        raise AppException("VALIDATION_ERROR", "身份导入类型仅支持 STUDENT 或 TEACHER")
    return normalized


def create_identity_import_scan_job(
    *, kind: str, source_file_id: int, filename: str, user: dict
) -> dict:
    kind_up = _kind(kind)
    tenant_id = jobs._tenant_id()  # noqa: SLF001
    actor_id = jobs._actor_id(user)  # noqa: SLF001
    adapter_ref = f"{kind_up}:{int(source_file_id)}"
    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.adapter_type == PENDING_ADAPTER,
            ImportJob.adapter_ref == adapter_ref,
            ImportJob.is_deleted.is_(False),
        )).first()
        if existing:
            jobs._assert_row_visible(existing, user)  # noqa: SLF001
            return refresh_identity_import_job(str(existing.id), user=user)
        row = ImportJob(
            tenant_id=tenant_id,
            module_code="SYSTEM",
            import_type=f"IDENTITY_{kind_up}",
            source_file_id=int(source_file_id),
            adapter_type=PENDING_ADAPTER,
            adapter_ref=adapter_ref,
            template_version="v1",
            status="SCANNING",
            operator_id=actor_id,
            operator_name=jobs._actor_name(user),  # noqa: SLF001
            expires_at=datetime.utcnow() + timedelta(hours=jobs.IMPORT_JOB_TTL_HOURS),
            source_snapshot_json={
                "fileName": str(filename or "identity_import.xlsx"),
                "kind": kind_up,
                "parseMode": "NORMALIZED_STAGING_PENDING",
            },
            result_json={"scanRequired": True, "parseStartedAt": None},
            created_by=actor_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        job_id = str(row.id)
    finally:
        db.close()
    return refresh_identity_import_job(job_id, user=user)


def _mark_failed(
    job_id: int,
    message: str,
    user: dict,
    *,
    visibility: str | None = None,
    module_code: str | None = None,
) -> dict:
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(  # noqa: SLF001
            db, job_id, user, lock=True, visibility=visibility, module_code=module_code,
        )
        row.status = "VALIDATION_FAILED"
        row.error_message = str(message or "身份导入预检失败")[:4000]
        row.version = int(row.version or 0) + 1
        row.result_json = {
            **dict(row.result_json or {}),
            "parseFinishedAt": datetime.utcnow().isoformat() + "Z",
        }
        db.commit()
        db.refresh(row)
        return jobs._import_row(row)  # noqa: SLF001
    finally:
        db.close()


def _file_state(db, row: ImportJob) -> tuple[FileObject, bool]:
    file_obj = db.scalars(select(FileObject).where(
        FileObject.id == int(row.source_file_id or 0),
        FileObject.tenant_id == int(row.tenant_id),
        FileObject.is_deleted.is_(False),
    )).first()
    if not file_obj:
        raise not_found("身份导入源文件不存在")
    scan = str(file_obj.scan_status or "NOT_REQUIRED").upper()
    ready = bool(is_downloadable_status(file_obj.status) and scan in READY_SCAN_STATES)
    return file_obj, ready


def refresh_identity_import_job(
    job_id: str,
    *,
    user: dict,
    visibility: str | None = None,
    module_code: str | None = None,
    worker_claimed: bool = False,
) -> dict:
    """Advance one identity job only after the source file is business-ready.

    ``worker_claimed`` is accepted only for the durable ``WORKER_CLAIMED`` state;
    it does not bypass tenant/owner checks and therefore cannot turn arbitrary jobs
    into worker-owned work.
    """
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(  # noqa: SLF001
            db, job_id, user, lock=True, visibility=visibility, module_code=module_code,
        )
        if row.adapter_type != PENDING_ADAPTER:
            return jobs._import_row(row)  # noqa: SLF001
        if not jobs._row_is_owned(row, user):  # noqa: SLF001
            return jobs._import_row(row)  # noqa: SLF001
        if worker_claimed and row.status != WORKER_CLAIMED:
            raise AppException("DATA_CONFLICT", "身份导入 worker claim 已失效", http_status=409)
        if not worker_claimed and row.status == WORKER_CLAIMED:
            # A live/background worker owns this transition. Browser/manual retries
            # must not race it; stale claims are recovered by the worker itself.
            return jobs._import_row(row)  # noqa: SLF001
        if row.expires_at and row.expires_at <= datetime.utcnow():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            return jobs._import_row(row)  # noqa: SLF001
        file_obj, ready = _file_state(db, row)
        scan = str(file_obj.scan_status or "NOT_REQUIRED").upper()
        if not ready:
            if scan in {"INFECTED", "ERROR", "FAILED"} or str(file_obj.status or "").upper() in {
                "REJECTED", "DELETED",
            }:
                row.status = "VALIDATION_FAILED"
                row.error_message = "源文件安全扫描失败或已被隔离，禁止解析"
                row.version = int(row.version or 0) + 1
                db.commit()
            else:
                row.status = "SCANNING"
                db.commit()
            return jobs._import_row(row)  # noqa: SLF001

        result = dict(row.result_json or {})
        started_raw = str(result.get("parseStartedAt") or "")
        if row.status == "PARSING" and started_raw:
            try:
                started = datetime.fromisoformat(started_raw.rstrip("Z"))
            except ValueError:
                started = datetime.min
            if (datetime.utcnow() - started).total_seconds() < PARSING_STALE_SECONDS:
                return jobs._import_row(row)  # noqa: SLF001
        row.status = "PARSING"
        row.error_message = None
        row.version = int(row.version or 0) + 1
        row.result_json = {
            **result,
            "parseStartedAt": datetime.utcnow().isoformat() + "Z",
            "workerClaimConsumed": bool(worker_claimed),
        }
        tenant_id = int(row.tenant_id)
        actor_id = jobs._actor_id(user)  # noqa: SLF001
        source_file_id = int(file_obj.id)
        file_key = str(file_obj.file_key)
        filename = str(
            (row.source_snapshot_json or {}).get("fileName")
            or file_obj.file_name
            or "identity_import.xlsx"
        )
        kind_up = _kind(
            (row.source_snapshot_json or {}).get("kind")
            or row.import_type.replace("IDENTITY_", "")
        )
        db.commit()
    finally:
        db.close()

    try:
        if kind_up == "STUDENT":
            from app.core.import_export_auth import enforce_student_import

            enforce_student_import(user)
        path = get_backend().fetch_local(file_key)
        if not path or not path.exists():
            raise AppException("FILE_NOT_FOUND", "身份导入源文件字节不存在")

        from app.services.identity_import_staging_service import (
            create_staging_batch,
            stage_identity_xlsx,
            validate_staging,
        )

        staged = stage_identity_xlsx(
            path=path,
            filename=filename,
            kind=kind_up,
            tenant_id=tenant_id,
            job_id=int(job_id),
            actor_id=actor_id,
        )
        report = validate_staging(
            user=user,
            tenant_id=tenant_id,
            job_id=int(job_id),
            parser_errors=list(staged.get("parserErrors") or []),
        )
        batch_result = create_staging_batch(
            user=user,
            tenant_id=tenant_id,
            job_id=int(job_id),
            filename=filename,
            file_sha256=str(staged["fileSha256"]),
            total_rows=int(staged["totalRows"]),
            staging_digest=str(staged["stagingDigest"]),
            report=report,
        )
        return _finalize_staged_job(
            job_id=int(job_id),
            source_file_id=source_file_id,
            kind=kind_up,
            staged=staged,
            batch_result=batch_result,
            user=user,
            visibility=visibility,
            module_code=module_code,
        )
    except Exception as exc:  # noqa: BLE001 - parser/validation errors are job state
        return _mark_failed(
            int(job_id), str(exc), user, visibility=visibility, module_code=module_code,
        )


def _finalize_staged_job(
    *,
    job_id: int,
    source_file_id: int,
    kind: str,
    staged: dict,
    batch_result: dict,
    user: dict,
    visibility: str | None = None,
    module_code: str | None = None,
) -> dict:
    from app.services.identity_import_staging_service import (
        STAGING_CHUNK_SIZE,
        build_staging_error_workbook,
    )

    batch_no = str(batch_result.get("batchNo") or "").strip()
    if not batch_no:
        raise AppException("SERVER_ERROR", "身份导入 staging 批次创建失败")
    errors = list(batch_result.get("errors") or [])
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(  # noqa: SLF001
            db, job_id, user, lock=True, visibility=visibility, module_code=module_code,
        )
        if row.adapter_type != PENDING_ADAPTER or row.status != "PARSING":
            return jobs._import_row(row)  # noqa: SLF001
        duplicate = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == row.tenant_id,
            ImportJob.adapter_type == jobs.IMPORT_ADAPTER_IDENTITY,
            ImportJob.adapter_ref == batch_no,
            ImportJob.id != row.id,
            ImportJob.is_deleted.is_(False),
        )).first()
        if duplicate:
            row.status = "CANCELLED"
            row.error_message = f"批次已由任务 {duplicate.id} 接管"
            row.version = int(row.version or 0) + 1
            db.commit()
            return jobs._import_row(row)  # noqa: SLF001

        row.adapter_type = jobs.IMPORT_ADAPTER_IDENTITY
        row.adapter_ref = batch_no
        row.status = "VALIDATED" if not errors else "VALIDATION_FAILED"
        row.total_rows = int(batch_result.get("total") or staged.get("totalRows") or 0)
        row.valid_rows = int(batch_result.get("valid") or 0)
        row.invalid_rows = int(batch_result.get("invalid") or 0)
        row.source_file_id = source_file_id
        row.source_snapshot_json = {
            "fileName": staged.get("fileName"),
            "fileSha256": staged.get("fileSha256"),
            "kind": kind,
            "roleTemplateVersion": batch_result.get("roleTemplateVersion"),
            "parseMode": "NORMALIZED_STAGING",
            "stagingAuthority": True,
            "stagingChunkSize": STAGING_CHUNK_SIZE,
            "stagingRows": int(staged.get("totalRows") or 0),
            "stagingDigest": staged.get("stagingDigest"),
        }
        row.result_json = {
            **dict(row.result_json or {}),
            "parseFinishedAt": datetime.utcnow().isoformat() + "Z",
            "batchNo": batch_no,
            "stagingAuthority": True,
        }
        row.error_message = "" if not errors else "服务端预检存在错误，请下载错误回执"
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        result = jobs._import_row(row)  # noqa: SLF001
    finally:
        db.close()

    if errors:
        receipt_bytes = build_staging_error_workbook(tenant_id=jobs._tenant_id(), job_id=job_id)  # noqa: SLF001
        file_id = jobs._write_generated_file(  # noqa: SLF001
            receipt_bytes,
            f"师生账号导入错误_{batch_no}.xlsx",
            biz_id=f"IMPORT:{job_id}:ERRORS",
            user=user,
            security_level="SENSITIVE",
        )
        jobs._create_export_job(  # noqa: SLF001
            export_type="IMPORT_ERROR_RECEIPT",
            purpose="导入预检错误回执",
            file_object_id=file_id,
            row_count=len(errors),
            user=user,
            adapter_type="IMPORT_JOB",
            adapter_ref=str(job_id),
        )
        db = get_sessionmaker()()
        try:
            current = jobs._owned_import(  # noqa: SLF001
                db, job_id, user, lock=True, visibility=visibility, module_code=module_code,
            )
            current.error_receipt_file_id = file_id
            current.version = int(current.version or 0) + 1
            db.commit()
            db.refresh(current)
            return jobs._import_row(current)  # noqa: SLF001
        finally:
            db.close()
    return result