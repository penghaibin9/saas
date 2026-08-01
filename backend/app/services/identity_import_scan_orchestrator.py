"""身份导入 FileObject 扫描后解析编排。

上传请求只登记隔离文件和 ImportJob；查询任务时在文件 CLEAN/AVAILABLE 后抢占 PARSING，
从存储路径流式校验/解析并把同一任务转换为既有 IDENTITY_IMPORT_BATCH adapter。
确认接口仍只信任 jobId + expectedVersion，不接受前端 rows。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob, ImportRowError
from app.models.file import FileObject
from app.services import data_exchange_job_service as jobs
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES
from app.services.identity_import_path_parser import parse_identity_xlsx_path
from app.services.storage import get_backend

PARSING_STALE_SECONDS = 5 * 60
PENDING_ADAPTER = "IDENTITY_IMPORT_FILE"


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
                "parseMode": "SCANNED_FILE_PATH",
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


def _mark_failed(job_id: int, message: str, user: dict) -> dict:
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)  # noqa: SLF001
        row.status = "VALIDATION_FAILED"
        row.error_message = str(message or "身份导入预检失败")[:4000]
        row.version = int(row.version or 0) + 1
        row.result_json = {**dict(row.result_json or {}), "parseFinishedAt": datetime.utcnow().isoformat() + "Z"}
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


def refresh_identity_import_job(job_id: str, *, user: dict) -> dict:
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)  # noqa: SLF001
        if row.adapter_type != PENDING_ADAPTER:
            return jobs._import_row(row)  # noqa: SLF001
        if row.expires_at and row.expires_at <= datetime.utcnow():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            return jobs._import_row(row)  # noqa: SLF001
        file_obj, ready = _file_state(db, row)
        scan = str(file_obj.scan_status or "NOT_REQUIRED").upper()
        if not ready:
            if scan in {"INFECTED", "ERROR", "FAILED"} or str(file_obj.status or "").upper() in {"REJECTED", "DELETED"}:
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
        row.result_json = {**result, "parseStartedAt": datetime.utcnow().isoformat() + "Z"}
        source_file_id = int(file_obj.id)
        filename = str((row.source_snapshot_json or {}).get("fileName") or file_obj.file_name or "identity_import.xlsx")
        kind_up = str((row.source_snapshot_json or {}).get("kind") or row.import_type.replace("IDENTITY_", ""))
        db.commit()
    finally:
        db.close()

    try:
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise AppException("FILE_NOT_FOUND", "身份导入源文件字节不存在")
        parsed = parse_identity_xlsx_path(path, filename, kind_up)
        if kind_up == "STUDENT":
            from app.core.import_export_auth import enforce_student_import

            enforce_student_import(user)
            payload = {"students": parsed["students"], "teachers": [], "atomic": True}
        else:
            payload = {"students": [], "teachers": parsed["teachers"], "atomic": True}
        from app.services.identity_import_file_service import create_batch
        from app.services.identity_import_service import preview_identity_import

        report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
        batch_result = create_batch(user, parsed, report)
        return _finalize_parsed_job(
            job_id=int(job_id),
            source_file_id=source_file_id,
            kind=kind_up,
            parsed=parsed,
            batch_result=batch_result,
            user=user,
        )
    except Exception as exc:  # noqa: BLE001 - parsing errors belong to the task state
        return _mark_failed(int(job_id), str(exc), user)


def _finalize_parsed_job(
    *, job_id: int, source_file_id: int, kind: str, parsed: dict, batch_result: dict, user: dict
) -> dict:
    from app.services.identity_import_file_service import build_error_workbook, get_batch

    batch_no = str(batch_result.get("batchNo") or "").strip()
    if not batch_no:
        raise AppException("SERVER_ERROR", "身份导入批次创建失败")
    errors = list(batch_result.get("errors") or [])
    relation_errors = list((batch_result.get("relations") or {}).get("errors") or [])
    all_errors = errors + relation_errors
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)  # noqa: SLF001
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
            return jobs._import_row(duplicate)  # noqa: SLF001

        db.execute(delete(ImportRowError).where(
            ImportRowError.tenant_id == row.tenant_id,
            ImportRowError.import_job_id == row.id,
        ))
        row.adapter_type = jobs.IMPORT_ADAPTER_IDENTITY
        row.adapter_ref = batch_no
        row.status = "VALIDATED" if not all_errors else "VALIDATION_FAILED"
        row.total_rows = int(batch_result.get("total") or parsed.get("totalRows") or 0)
        row.valid_rows = int(batch_result.get("valid") or 0)
        row.invalid_rows = int(batch_result.get("invalid") or len(all_errors))
        row.source_file_id = source_file_id
        row.source_snapshot_json = {
            "fileName": parsed.get("fileName"),
            "fileSha256": parsed.get("fileSha256"),
            "kind": kind,
            "roleTemplateVersion": batch_result.get("roleTemplateVersion"),
            "parseMode": "SCANNED_FILE_PATH",
        }
        row.result_json = {
            **dict(row.result_json or {}),
            "parseFinishedAt": datetime.utcnow().isoformat() + "Z",
            "batchNo": batch_no,
        }
        row.error_message = "" if not all_errors else "服务端预检存在错误，请下载错误回执"
        row.version = int(row.version or 0) + 1
        for item in all_errors:
            db.add(ImportRowError(
                tenant_id=row.tenant_id,
                import_job_id=row.id,
                sheet_name="业务关系" if item in relation_errors else "导入模板",
                row_no=int(item.get("row") or 0) or None,
                field_code=str(item.get("field") or "")[:100] or None,
                error_code=str(item.get("errorCode") or "VALIDATION_ERROR")[:80],
                error_message=str(item.get("message") or item.get("error") or "校验失败")[:1000],
                raw_snapshot_json={"entity": item.get("entity"), "row": item.get("row")},
                created_by=jobs._actor_id(user),  # noqa: SLF001
            ))
        db.commit()
        db.refresh(row)
        result = jobs._import_row(row)  # noqa: SLF001
    finally:
        db.close()

    if all_errors:
        entry = get_batch(user, jobs._tenant_id(), batch_no)  # noqa: SLF001
        receipt_bytes = build_error_workbook(entry)
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
            row_count=len(all_errors),
            user=user,
            adapter_type="IMPORT_JOB",
            adapter_ref=str(job_id),
        )
        db = get_sessionmaker()()
        try:
            current = jobs._owned_import(db, job_id, user, lock=True)  # noqa: SLF001
            current.error_receipt_file_id = file_id
            current.version = int(current.version or 0) + 1
            db.commit()
            db.refresh(current)
            return jobs._import_row(current)  # noqa: SLF001
        finally:
            db.close()
    return result
