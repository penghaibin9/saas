"""I1/I2 canonical identity-import orchestration without new schema.

Creation is side-effect free beyond durable job registration. GET/read paths
never parse. Parsing is an explicit worker command, which delegates the frozen
scanner/parser implementation after ownership and scan gates have been checked.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob
from app.services import data_exchange_job_service as jobs
from app.services import identity_import_scan_orchestrator as legacy

PENDING_ADAPTER = legacy.PENDING_ADAPTER


def _kind(value: str) -> str:
    return legacy._kind(value)  # noqa: SLF001


def create_identity_import_job(*, kind: str, source_file_id: int, filename: str, user: dict) -> dict:
    """Register SCANNING job only; never parse in the upload request."""
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
            return jobs._import_row(existing)  # noqa: SLF001
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
                "parseMode": "WORKER_AFTER_FILE_SCAN",
            },
            result_json={
                "scanRequired": True,
                "parseStartedAt": None,
                "workerRequired": True,
            },
            created_by=actor_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jobs._import_row(row)  # noqa: SLF001
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def read_identity_import_job(
    job_id: str,
    *,
    user: dict,
    visibility: str = "OWN",
    module_code: str = "",
) -> dict:
    """Pure read. This function must never call scanner/parser orchestration."""
    return jobs.get_import_job(
        job_id,
        user=user,
        visibility=visibility,
        module_code=module_code,
    )


def process_identity_import_job(job_id: str, *, user: dict) -> dict:
    """Explicit worker command for one owned identity ImportJob."""
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=False)  # noqa: SLF001
        if row.adapter_type != PENDING_ADAPTER:
            return jobs._import_row(row)  # noqa: SLF001
        if not jobs._row_is_owned(row, user):  # noqa: SLF001
            raise not_found("身份导入任务不存在")
        if row.status not in {"SCANNING", "PARSING", "FAILED", "VALIDATION_FAILED"}:
            return jobs._import_row(row)  # noqa: SLF001
    finally:
        db.close()
    return legacy.refresh_identity_import_job(job_id, user=user)


def find_identity_job_by_batch(batch_no: str, *, user: dict) -> dict:
    """Legacy confirm adapter: resolve old batchNo to the canonical ImportJob."""
    batch = str(batch_no or "").strip()
    if not batch:
        raise AppException("VALIDATION_ERROR", "缺少 batchNo/jobId")
    tenant_id = jobs._tenant_id()  # noqa: SLF001
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.adapter_type == jobs.IMPORT_ADAPTER_IDENTITY,
            ImportJob.adapter_ref == batch,
            ImportJob.is_deleted.is_(False),
        )).first()
        if row is None:
            # New clients may pass canonical jobId into the legacy-shaped method.
            if batch.isdigit():
                row = jobs._owned_import(db, batch, user)  # noqa: SLF001
            else:
                raise not_found("导入批次不存在或尚未完成安全扫描与预检")
        jobs._assert_row_visible(row, user)  # noqa: SLF001
        return jobs._import_row(row)  # noqa: SLF001
    finally:
        db.close()
