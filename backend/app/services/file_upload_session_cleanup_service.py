"""过期未完成上传会话的可恢复清理。

先提交 EXPIRE_PENDING，再在行锁内删除并核验对象，最后提交 EXPIRED 并释放配额预留。
删除失败保存 EXPIRE_FAILED，且继续占用预留；下轮 worker 可重试，不会伪装已回收容量。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.services.storage import get_backend


def _session_ids(*, tenant_id: int, now: datetime, limit: int) -> list[int]:
    from app.models.file import FileUploadSession

    db = get_sessionmaker()()
    try:
        return [
            int(value)
            for value in db.scalars(select(FileUploadSession.id).where(
                FileUploadSession.tenant_id == tenant_id,
                FileUploadSession.is_deleted.is_(False),
                FileUploadSession.expires_at.is_not(None),
                FileUploadSession.expires_at <= now,
                FileUploadSession.status.in_([
                    "CREATED", "UPLOADING", "EXPIRE_PENDING", "EXPIRE_FAILED",
                ]),
            ).order_by(FileUploadSession.id).limit(max(1, min(limit, 5000)))).all()
        ]
    finally:
        db.close()


def expire_upload_sessions(*, tenant_id: int, limit: int = 500) -> dict:
    from app.models.file import FileUploadSession
    from app.services.file_storage_quota_reservation_service import release_quota

    now = datetime.utcnow()
    expired = deleted_objects = failed = 0
    errors: list[dict] = []
    for session_id in _session_ids(tenant_id=tenant_id, now=now, limit=limit):
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(FileUploadSession).where(
                FileUploadSession.id == session_id,
                FileUploadSession.tenant_id == tenant_id,
                FileUploadSession.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row or row.status == "COMPLETED":
                db.rollback()
                continue
            row.status = "EXPIRE_PENDING"
            row.updated_at = now
            db.commit()
        finally:
            db.close()

        db = get_sessionmaker()()
        try:
            row = db.scalars(select(FileUploadSession).where(
                FileUploadSession.id == session_id,
                FileUploadSession.tenant_id == tenant_id,
                FileUploadSession.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row or row.status == "COMPLETED":
                db.rollback()
                continue
            object_key = str((row.metadata_json or {}).get("objectKey") or "")
            if object_key:
                backend = get_backend()
                backend.delete(object_key)
                if backend.exists(object_key):
                    raise RuntimeError("过期上传对象删除后仍可被存储后端发现")
                deleted_objects += 1
            row.status = "EXPIRED"
            row.updated_at = now
            release_quota(
                f"cos-session:{row.session_key}",
                reason="COS_UPLOAD_SESSION_EXPIRED",
                tenant_id=tenant_id,
                db=db,
            )
            db.commit()
            expired += 1
        except Exception as exc:
            db.rollback()
            fail_db = get_sessionmaker()()
            try:
                row = fail_db.get(FileUploadSession, session_id, with_for_update=True)
                if row and row.status != "COMPLETED":
                    row.status = "EXPIRE_FAILED"
                    row.updated_at = now
                    fail_db.commit()
            finally:
                fail_db.close()
            failed += 1
            errors.append({"sessionId": str(session_id), "error": str(exc)[:500]})
        finally:
            db.close()

    return {
        "tenantId": tenant_id,
        "expiredSessions": expired,
        "deletedObjects": deleted_objects,
        "failed": failed,
        "errors": errors,
    }
