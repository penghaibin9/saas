"""公共文件扫描队列、业务放行门禁、健康检查和失败重试。"""
from __future__ import annotations

import socket
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker
from app.services.clamav_client import ClamAVClient, ClamAVError, ClamAVUnavailable
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_config import get_file_scan_config
from app.services.file_scan_constants import (
    JOB_DEAD,
    JOB_PENDING,
    JOB_RETRY,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    READY_SCAN_STATES,
    SCAN_CLEAN,
    SCAN_ERROR,
    SCAN_INFECTED,
    SCAN_JOB_TYPE,
    SCAN_NOT_REQUIRED,
    SCAN_PENDING,
    SCAN_RUNNING,
)
from app.services.storage import get_backend


def _now() -> datetime:
    return datetime.utcnow()


def enqueue_file_scan(db, file_obj) -> None:
    """同一文件只保留一个可复用扫描任务；提交者事务内调用。"""
    if not getattr(file_obj, "scan_required", False):
        return
    from app.models.file import FileJob

    config = get_file_scan_config()
    key = f"FILE_SCAN:{file_obj.id}"
    job = db.scalars(select(FileJob).where(
        FileJob.tenant_id == file_obj.tenant_id,
        FileJob.dedupe_key == key,
        FileJob.is_deleted.is_(False),
    )).first()
    if job is None:
        job = FileJob(
            tenant_id=file_obj.tenant_id,
            job_type=SCAN_JOB_TYPE,
            file_id=file_obj.id,
            dedupe_key=key,
            status=JOB_PENDING,
            attempts=0,
            max_attempts=config.max_attempts,
            available_at=_now(),
            payload_json={"fileId": str(file_obj.id)},
        )
        db.add(job)
    elif job.status in {JOB_DEAD, JOB_SUCCEEDED}:
        job.status = JOB_PENDING
        job.max_attempts = max(
            int(job.max_attempts or 0),
            int(job.attempts or 0) + config.max_attempts,
        )
        job.available_at = _now()
        job.locked_at = None
        job.locked_by = None
        job.last_error = None
        job.result_json = None
    file_obj.status = "QUARANTINED"
    file_obj.storage_zone = "QUARANTINE"
    file_obj.scan_status = SCAN_PENDING


def assert_file_ready_for_business(
    file_id: str,
    *,
    user: dict | None = None,
    biz_type: str | None = None,
    biz_id: str | None = None,
):
    """业务提交、绑定和下载前的统一 fail-closed 门禁。"""
    if not db_enabled() or not str(file_id).isdigit():
        from app.services import file_service

        meta = file_service._MEM_REGISTRY.get(file_id)  # noqa: SLF001
        if not meta:
            raise not_found("文件不存在")
        status = str(meta.get("status") or "").upper()
        scan_status = str(meta.get("scanStatus") or SCAN_NOT_REQUIRED).upper()
        if not is_downloadable_status(status) or scan_status not in READY_SCAN_STATES:
            raise AppException("FILE_NOT_READY", "文件尚未完成安全扫描，暂不可提交", http_status=409)
        return meta

    tenant_id = int(current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝使用文件")
    from app.models.file import FileObject
    from app.services import file_service

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
        actor = user or get_current_user_ctx() or {}
        if not row or not file_service.authorize_file_access(actor, row, "bind"):
            raise not_found("文件不存在或无权访问")
        if biz_type and row.biz_type and row.biz_type.upper() != biz_type.upper():
            raise AppException("DATA_CONFLICT", "文件用途与当前业务不一致")
        if biz_id and row.biz_id and str(row.biz_id) != str(biz_id):
            raise AppException("DATA_CONFLICT", "文件已绑定其他业务对象")
        scan_status = (row.scan_status or SCAN_NOT_REQUIRED).upper()
        if row.scan_required and scan_status == SCAN_INFECTED:
            raise AppException("FILE_REJECTED", "文件包含恶意内容，已拒绝", http_status=422)
        if row.scan_required and scan_status == SCAN_ERROR:
            raise AppException("FILE_SCAN_UNAVAILABLE", "文件安全扫描失败，暂不可提交", http_status=503)
        if not is_downloadable_status(row.status) or scan_status not in READY_SCAN_STATES:
            raise AppException("FILE_NOT_READY", "文件尚未完成安全扫描，暂不可提交", http_status=409)
        return row
    finally:
        db.close()


def _claim_one(worker_id: str) -> int | None:
    from app.models.file import FileJob

    config = get_file_scan_config()
    now = _now()
    stale_before = now - timedelta(seconds=config.stale_lock_seconds)
    db = get_sessionmaker()()
    try:
        stmt = (
            select(FileJob)
            .where(
                FileJob.job_type == SCAN_JOB_TYPE,
                FileJob.is_deleted.is_(False),
                FileJob.available_at <= now,
                or_(
                    FileJob.status.in_([JOB_PENDING, JOB_RETRY]),
                    (FileJob.status == JOB_RUNNING) & (FileJob.locked_at < stale_before),
                ),
            )
            .order_by(FileJob.available_at, FileJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = db.scalars(stmt).first()
        if not job:
            db.rollback()
            return None
        job.status = JOB_RUNNING
        job.attempts = int(job.attempts or 0) + 1
        job.locked_at = now
        job.locked_by = worker_id
        job.last_error = None
        db.commit()
        return int(job.id)
    finally:
        db.close()


def _engine_parts(version: str) -> tuple[str | None, str | None]:
    pieces = (version or "").split("/")
    return (
        pieces[0].strip() or None,
        pieces[1].strip() if len(pieces) > 1 else None,
    )


def _complete_job(job_id: int, client: ClamAVClient | None = None) -> dict[str, Any]:
    from app.models.file import FileJob, FileObject, FileScanRecord

    config = get_file_scan_config()
    db = get_sessionmaker()()
    started = _now()
    try:
        job = db.get(FileJob, job_id)
        if not job or job.status != JOB_RUNNING:
            return {"processed": False, "reason": "job-not-running"}
        row = db.scalars(select(FileObject).where(
            FileObject.id == job.file_id,
            FileObject.tenant_id == job.tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
        if not row:
            job.status = JOB_DEAD
            job.last_error = "file object missing"
            db.commit()
            return {"processed": False, "reason": "file-missing"}

        row.scan_status = SCAN_RUNNING
        row.scan_attempts = int(job.attempts or 0)
        db.commit()

        if not config.enabled:
            raise ClamAVUnavailable("ClamAV is disabled")
        scanner = client or ClamAVClient(config)
        path = get_backend().fetch_local(row.file_key)
        if not path or not path.exists():
            raise ClamAVError("storage object missing")
        version = scanner.version()
        result = scanner.scan_path(path)
        engine_version, signature_version = _engine_parts(version)
        completed = _now()

        db.add(FileScanRecord(
            tenant_id=row.tenant_id,
            file_id=row.id,
            attempt=int(job.attempts or 0),
            engine="CLAMAV",
            engine_version=engine_version,
            signature_version=signature_version,
            result=SCAN_CLEAN if result.clean else SCAN_INFECTED,
            threat_name=result.signature,
            started_at=started,
            completed_at=completed,
            details_json={"raw": result.raw},
        ))
        row.scan_engine = "CLAMAV"
        row.scan_engine_version = engine_version
        row.scan_signature_version = signature_version
        row.scan_last_error = None
        row.scanned_at = completed
        if result.clean:
            row.scan_status = SCAN_CLEAN
            row.status = "AVAILABLE"
            row.storage_zone = "ACTIVE"
            row.available_at = completed
            row.rejected_at = None
            job.status = JOB_SUCCEEDED
            job.result_json = {"scanStatus": SCAN_CLEAN}
        else:
            row.scan_status = SCAN_INFECTED
            row.status = "REJECTED"
            row.storage_zone = "REJECTED"
            row.rejected_at = completed
            job.status = JOB_SUCCEEDED
            job.result_json = {
                "scanStatus": SCAN_INFECTED,
                "threat": result.signature,
            }
        job.locked_at = None
        job.locked_by = None
        db.commit()
        return {
            "processed": True,
            "fileId": str(row.id),
            "scanStatus": row.scan_status,
        }
    except Exception as exc:  # noqa: BLE001 - worker must persist every failure
        db.rollback()
        job = db.get(FileJob, job_id)
        if not job:
            return {"processed": False, "reason": str(exc)}
        row = db.get(FileObject, job.file_id) if job.file_id else None
        completed = _now()
        if row:
            exhausted = int(job.attempts or 0) >= int(job.max_attempts or 1)
            row.status = "QUARANTINED"
            row.storage_zone = "QUARANTINE"
            row.scan_status = SCAN_ERROR if exhausted else SCAN_PENDING
            row.scan_last_error = str(exc)[:2000]
            row.scan_attempts = int(job.attempts or 0)
            db.add(FileScanRecord(
                tenant_id=row.tenant_id,
                file_id=row.id,
                attempt=int(job.attempts or 0),
                engine="CLAMAV",
                result=SCAN_ERROR,
                started_at=started,
                completed_at=completed,
                error_code=exc.__class__.__name__[:80],
                error_message=str(exc)[:4000],
            ))
        if int(job.attempts or 0) >= int(job.max_attempts or 1):
            job.status = JOB_DEAD
        else:
            job.status = JOB_RETRY
            delay = config.retry_base_seconds * (2 ** max(0, int(job.attempts or 1) - 1))
            job.available_at = completed + timedelta(seconds=min(delay, 3600))
        job.last_error = str(exc)[:4000]
        job.locked_at = None
        job.locked_by = None
        db.commit()
        return {
            "processed": True,
            "error": str(exc),
            "jobStatus": job.status,
        }
    finally:
        db.close()


def process_next_scan_job(
    worker_id: str | None = None,
    client: ClamAVClient | None = None,
) -> dict[str, Any]:
    worker = worker_id or f"{socket.gethostname()}:{id(client)}"
    job_id = _claim_one(worker)
    if job_id is None:
        return {"processed": False, "reason": "empty"}
    return _complete_job(job_id, client=client)


def retry_file_scan(file_id: str, *, user: dict | None = None) -> dict[str, Any]:
    from app.core.permissions import has_permission, is_super_admin
    from app.models.file import FileJob, FileObject

    actor = user or get_current_user_ctx() or {}
    if not (
        is_super_admin(actor)
        or has_permission(actor, "systemAdmin.file.manage")
        or has_permission(actor, "*")
    ):
        raise AppException("NO_PERMISSION", "仅文件管理员可重试安全扫描")
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("文件不存在")
        if row.scan_status == SCAN_INFECTED:
            raise AppException("FILE_REJECTED", "感染文件不可人工放行")
        row.scan_required = True
        row.scan_status = SCAN_PENDING
        row.status = "QUARANTINED"
        row.storage_zone = "QUARANTINE"
        row.scan_last_error = None
        key = f"FILE_SCAN:{row.id}"
        job = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.dedupe_key == key,
            FileJob.is_deleted.is_(False),
        )).first()
        if job:
            config = get_file_scan_config()
            job.status = JOB_PENDING
            job.max_attempts = max(
                int(job.max_attempts or 0),
                int(job.attempts or 0) + config.max_attempts,
            )
            job.available_at = _now()
            job.locked_at = None
            job.locked_by = None
            job.last_error = None
        else:
            enqueue_file_scan(db, row)
        db.commit()
        return {
            "fileId": str(row.id),
            "scanStatus": row.scan_status,
            "status": row.status,
        }
    finally:
        db.close()


def file_scan_status(file_id: str, *, user: dict | None = None) -> dict[str, Any]:
    from app.models.file import FileObject
    from app.services import file_service

    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )).first()
        actor = user or get_current_user_ctx() or {}
        if not row or not file_service.authorize_file_access(actor, row, "meta"):
            raise not_found("文件不存在或无权访问")
        scan_status = row.scan_status or SCAN_NOT_REQUIRED
        return {
            "fileId": str(row.id),
            "status": row.status,
            "scanRequired": bool(row.scan_required),
            "scanStatus": scan_status,
            "scanAttempts": int(row.scan_attempts or 0),
            "scanEngine": row.scan_engine,
            "scanLastError": row.scan_last_error,
            "readyForBusiness": (
                is_downloadable_status(row.status) and scan_status in READY_SCAN_STATES
            ),
            "scannedAt": (
                row.scanned_at.isoformat(timespec="seconds")
                if row.scanned_at
                else None
            ),
        }
    finally:
        db.close()


def health_snapshot() -> dict[str, Any]:
    from app.models.file import FileJob

    config = get_file_scan_config()
    engine_ok = False
    engine_error = None
    engine_version = None
    if config.enabled:
        try:
            client = ClamAVClient(config)
            engine_ok = client.ping()
            engine_version = client.version() if engine_ok else None
        except Exception as exc:  # noqa: BLE001
            engine_error = str(exc)
    else:
        engine_error = "disabled"

    tenant_id = int(current_tenant_id() or 0)
    queue = dead = 0
    if db_enabled():
        db = get_sessionmaker()()
        try:
            base = [
                FileJob.job_type == SCAN_JOB_TYPE,
                FileJob.is_deleted.is_(False),
            ]
            if tenant_id:
                base.append(FileJob.tenant_id == tenant_id)
            queue = int(db.scalar(
                select(func.count()).select_from(FileJob).where(
                    *base,
                    FileJob.status.in_([JOB_PENDING, JOB_RETRY, JOB_RUNNING]),
                )
            ) or 0)
            dead = int(db.scalar(
                select(func.count()).select_from(FileJob).where(
                    *base,
                    FileJob.status == JOB_DEAD,
                )
            ) or 0)
        finally:
            db.close()
    return {
        "enabled": config.enabled,
        "required": config.required,
        "engine": "CLAMAV",
        "engineHealthy": engine_ok,
        "engineVersion": engine_version,
        "engineError": engine_error,
        "queueDepth": queue,
        "deadJobs": dead,
        "failClosed": True,
    }
