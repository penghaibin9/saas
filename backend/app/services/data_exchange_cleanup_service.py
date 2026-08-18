"""数据交换任务过期清理（严格当前租户范围）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services.storage import get_backend


def cleanup_current_tenant_expired_jobs(*, limit: int = 200) -> dict:
    """学校端维护只处理当前 tenant；I3 staging 随过期 ImportJob 一并软删。"""
    from app.models.data_exchange import ExportJob, IdentityImportStagingRow, ImportJob
    from app.models.file import FileObject

    try:
        tenant_id = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        tenant_id = 0
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文，拒绝清理任务")

    now = datetime.utcnow()
    db = get_sessionmaker()()
    import_count = export_count = file_count = staging_count = 0
    try:
        imports = db.scalars(select(ImportJob).where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.is_deleted.is_(False),
            ImportJob.expires_at.is_not(None),
            ImportJob.expires_at <= now,
            ImportJob.status.notin_(["SUCCEEDED", "EXPIRED"]),
        ).order_by(ImportJob.id).limit(limit)).all()
        for row in imports:
            row.status = "EXPIRED"
            row.lease_token = None
            row.lease_started_at = None
            row.version = int(row.version or 0) + 1
            result = db.execute(update(IdentityImportStagingRow).where(
                IdentityImportStagingRow.tenant_id == tenant_id,
                IdentityImportStagingRow.import_job_id == int(row.id),
                IdentityImportStagingRow.is_deleted.is_(False),
            ).values(is_deleted=True, version=IdentityImportStagingRow.version + 1))
            staging_count += int(result.rowcount or 0)
            import_count += 1

        exports = db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.is_deleted.is_(False),
            ExportJob.expires_at.is_not(None),
            ExportJob.expires_at <= now,
            ExportJob.status == "SUCCEEDED",
        ).order_by(ExportJob.id).limit(limit)).all()
        for row in exports:
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
            if row.file_object_id:
                file_row = db.scalars(select(FileObject).where(
                    FileObject.id == row.file_object_id,
                    FileObject.tenant_id == tenant_id,
                    FileObject.is_deleted.is_(False),
                )).first()
                if file_row:
                    try:
                        get_backend().delete(file_row.file_key)
                    except Exception as exc:
                        row.status = "SUCCEEDED"
                        row.error_message = f"过期字节清理失败：{exc}"[:4000]
                        continue
                    file_row.is_deleted = True
                    file_row.status = "DELETED"
                    file_row.version = int(file_row.version or 0) + 1
                    file_count += 1
            export_count += 1
        db.commit()
        return {
            "tenantId": str(tenant_id),
            "expiredImports": import_count,
            "expiredExports": export_count,
            "deletedFiles": file_count,
            "expiredStagingRows": staging_count,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
