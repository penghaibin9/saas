"""统一 ImportJob 确认分派。

身份账号、老系统迁移与已迁移教务作业均只接受 jobId + expectedVersion；真正写入继续委托原业务
adapter，公共层负责租户、所有者、版本、过期、文件安全门、任务租约与结果投影。
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services import data_exchange_job_service as jobs


def _begin_adapter_confirm(job_id: str, expected_version: int, user: dict) -> tuple[str, str, str]:
    lease = secrets.token_hex(32)
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)
        if row.status == "SUCCEEDED":
            return row.adapter_type, row.adapter_ref, "ALREADY_DONE"
        if row.expires_at and row.expires_at <= jobs._now():
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            db.commit()
            raise AppException("DATA_CONFLICT", "导入任务已过期，请重新上传预检")
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "任务版本已变化，请刷新后重试")
        if row.invalid_rows or row.status == "VALIDATION_FAILED":
            raise AppException("VALIDATION_ERROR", "该任务存在预检错误，禁止确认导入")
        if row.status == "CONFIRMING" and row.lease_started_at \
                and row.lease_started_at > jobs._now() - timedelta(seconds=jobs.LEASE_STALE_SECONDS):
            raise AppException("DATA_CONFLICT", "该任务正在另一服务实例确认，请稍后刷新")
        if row.status not in {"VALIDATED", "CONFIRMING"}:
            raise AppException("DATA_CONFLICT", f"当前任务状态 {row.status} 不允许确认")
        row.status = "CONFIRMING"
        row.lease_token = lease
        row.lease_started_at = jobs._now()
        row.error_message = None
        row.version = int(row.version or 0) + 1
        adapter_type, adapter_ref = row.adapter_type, row.adapter_ref
        db.commit()
        return adapter_type, adapter_ref, lease
    finally:
        db.close()


def _finish(job_id: str, lease: str, result: dict, user: dict) -> dict:
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)
        if row.status == "SUCCEEDED":
            return jobs._import_row(row)
        if row.lease_token != lease:
            raise AppException("DATA_CONFLICT", "导入任务确认租约已失效")
        row.status = "SUCCEEDED"
        row.confirmed_rows = int(
            result.get("createdCount")
            or result.get("insertedRows")
            or result.get("confirmedRows")
            or row.valid_rows
            or 0
        )
        row.confirmed_at = jobs._now()
        row.result_json = result
        row.lease_token = None
        row.lease_started_at = None
        row.error_message = None
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return jobs._import_row(row)
    finally:
        db.close()


def _release(job_id: str, lease: str, error: Exception, user: dict) -> None:
    db = get_sessionmaker()()
    try:
        row = jobs._owned_import(db, job_id, user, lock=True)
        if row.lease_token == lease:
            row.status = "VALIDATED"
            row.lease_token = None
            row.lease_started_at = None
            row.error_message = str(error)[:4000]
            row.version = int(row.version or 0) + 1
            db.commit()
    finally:
        db.close()


def confirm_import_job(
    job_id: str,
    *,
    expected_version: int,
    user: dict,
    idempotency_key: str | None = None,
) -> dict:
    """按 adapter 类型分派；所有调用者只能提供统一任务编号与任务版本。"""
    db = get_sessionmaker()()
    try:
        current = jobs._owned_import(db, job_id, user)
        adapter_type = current.adapter_type
        import_type = current.import_type
        if current.status == "SUCCEEDED":
            return jobs._import_row(current)
    finally:
        db.close()

    if adapter_type == jobs.IMPORT_ADAPTER_IDENTITY:
        return jobs.confirm_identity_import_job(
            job_id,
            expected_version=expected_version,
            user=user,
            idempotency_key=idempotency_key,
        )

    adapter_type, adapter_ref, lease = _begin_adapter_confirm(job_id, expected_version, user)
    if lease == "ALREADY_DONE":
        db = get_sessionmaker()()
        try:
            return jobs._import_row(jobs._owned_import(db, job_id, user))
        finally:
            db.close()
    try:
        db = get_sessionmaker()()
        try:
            row = jobs._owned_import(db, job_id, user)
            source_file_id = str(row.source_file_id or "")
        finally:
            db.close()
        if not source_file_id:
            raise AppException("DATA_CONFLICT", "导入任务缺少原始文件，请重新上传")
        from app.services.file_scan_service import assert_file_ready_for_business
        assert_file_ready_for_business(source_file_id, user=user)

        if adapter_type == jobs.IMPORT_ADAPTER_MIGRATION:
            from app.services import migration_import_service as migration
            result = migration.confirm(adapter_ref)
            return _finish(job_id, lease, result, user)
        if adapter_type == jobs.IMPORT_ADAPTER_EXCEL and import_type in {
            "ACADEMIC_ROSTER", "ACADEMIC_GRADE", "ACADEMIC_SCHEDULE",
        }:
            from app.modules.academic_affairs.services import academic_file_exchange_service as academic
            result = academic.confirm_academic_import(job_id, lease=lease, user=user)
            return _finish(job_id, lease, result, user)
        if adapter_type == jobs.IMPORT_ADAPTER_EXCEL:
            raise AppException(
                "DATA_CONFLICT",
                "该 Excel 作业尚未迁移到服务端权威确认，请使用对应业务入口",
            )
        raise AppException("DATA_CONFLICT", "未知导入 adapter，拒绝确认")
    except Exception as exc:
        _release(job_id, lease, exc, user)
        raise
