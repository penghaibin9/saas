"""I2 confirmation gate over the frozen Data Exchange confirm implementation."""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import data_exchange_confirm_legacy as _legacy


def _normalize_identity_source_user_binding(source_file_id: str, user: dict) -> None:
    """Normalize pre-canonical USER bindings without widening file access.

    Historical uploads stored the token-shaped subject (for example ``db-2`` or
    ``u_2``), while the file resolver compares the canonical numeric actor id.
    Identity confirmation may repair that representation only when the source
    FileObject belongs to the same tenant and the same resolved uploader.  A
    different owner, tenant or non-identity source is intentionally untouched and
    will continue to fail closed in the normal file-ready authorization gate.
    """
    raw_file_id = str(source_file_id or "").strip()
    if not raw_file_id.isdigit():
        return

    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding, FileObject
    from app.services import data_exchange_job_service as jobs

    tenant_id = jobs._tenant_id()  # noqa: SLF001 - same Data Exchange authority
    actor_id = jobs._actor_id(user)  # noqa: SLF001 - canonical server-side actor id
    if not actor_id:
        return

    db = get_sessionmaker()()
    try:
        file_obj = db.scalars(select(FileObject).where(
            FileObject.id == int(raw_file_id),
            FileObject.tenant_id == int(tenant_id),
            FileObject.owner_user_id == int(actor_id),
            FileObject.biz_type == "DATA_IMPORT_SOURCE",
            FileObject.is_deleted.is_(False),
        )).first()
        if file_obj is None:
            return

        aliases = {str(actor_id), f"db-{actor_id}", f"u_{actor_id}"}
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == int(tenant_id),
            FileBinding.file_id == int(file_obj.id),
            FileBinding.biz_type == "DATA_IMPORT_SOURCE",
            FileBinding.subject_type == "USER",
            FileBinding.is_deleted.is_(False),
        )).all()
        changed = False
        for binding in bindings:
            subject = str(binding.subject_id or "").strip()
            if subject in aliases and subject != str(actor_id):
                binding.subject_id = str(actor_id)
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


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
    _normalize_identity_source_user_binding(str(item.get("sourceFileId") or ""), user)
    return _legacy.confirm_import_job(
        job_id,
        expected_version=expected_version,
        user=user,
        idempotency_key=idempotency_key,
    )


def confirm_migration_import_job(*args, **kwargs):
    return _legacy.confirm_migration_import_job(*args, **kwargs)


def confirm_academic_import_job(*args, **kwargs):
    """显式 Academic canonical confirm 入口。

    frozen legacy 层继续持有统一任务租约、FileObject READY gate、幂等完成投影；
    其 Academic whitelist 唯一委托
    ``academic_file_exchange_service.confirm_academic_import`` 重读同一文件并执行领域事务。
    """
    return _legacy.confirm_import_job(*args, **kwargs)


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
        "ACADEMIC_COURSE_CATALOG",
    }:
        return confirm_academic_import_job(*args, **kwargs)
    return _legacy.confirm_import_job(*args, **kwargs)


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
