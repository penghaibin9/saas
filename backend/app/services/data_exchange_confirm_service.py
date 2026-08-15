"""I2 confirmation gate over the frozen Data Exchange confirm implementation."""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import data_exchange_confirm_legacy as _legacy


def confirm_identity_import_job(
    job_id: str,
    *,
    expected_version: int,
    user: dict,
    idempotency_key: str | None,
) -> dict:
    from app.services import data_exchange_job_service as jobs

    item = jobs.get_import_job(job_id, user=user)
    if str(item.get("status") or "").upper() != "VALIDATED":
        raise AppException(
            "IMPORT_NOT_VALIDATED",
            "导入任务尚未完成安全扫描与服务端预检，禁止确认",
            http_status=409,
            details={"status": item.get("status")},
        )
    if int(item.get("invalidRows") or 0) > 0:
        raise AppException("IMPORT_HAS_ERRORS", "预检存在错误行，禁止确认", http_status=409)
    if int(item.get("validRows") or 0) <= 0:
        raise AppException("IMPORT_EMPTY", "没有可确认导入的有效数据行", http_status=409)
    return _legacy.confirm_identity_import_job(
        job_id,
        expected_version=expected_version,
        user=user,
        idempotency_key=idempotency_key,
    )


def confirm_migration_import_job(*args, **kwargs):
    return _legacy.confirm_migration_import_job(*args, **kwargs)


def confirm_import_job(*args, **kwargs):
    job_id = str(args[0] if args else kwargs.get("job_id") or "")
    from app.services import data_exchange_job_service as jobs

    item = jobs.get_import_job(job_id, user=kwargs.get("user") or {})
    adapter_type = str(item.get("adapterType") or "")
    import_type = str(item.get("importType") or "")
    if adapter_type in {jobs.IMPORT_ADAPTER_IDENTITY, jobs.PENDING_IDENTITY_ADAPTER}:
        return confirm_identity_import_job(*args, **kwargs)
    if adapter_type == jobs.IMPORT_ADAPTER_EXCEL and import_type in {
        "ACADEMIC_ROSTER",
        "ACADEMIC_GRADE",
        "ACADEMIC_SCHEDULE",
    }:
        return _legacy.confirm_import_job(*args, **kwargs)
    return _legacy.confirm_import_job(*args, **kwargs)


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
