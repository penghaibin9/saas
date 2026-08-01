"""阶段 9：事务安全、可恢复的文件保留清理。

删除顺序：
1. 行锁复核保留期、法律保留和业务引用，提交 ``DELETE_PENDING``，阻止新的业务使用；
2. 再次行锁复核，在锁内删除物理对象并用 exists() 核验；
3. 提交 ``DELETED`` 终态。若终态提交失败，下轮会幂等重试；若删除失败，保存
   ``DELETE_FAILED`` 和 FileJob 错误，不伪装已回收容量。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.session import get_sessionmaker


def _candidate_ids(*, tenant_id: int, now: datetime, limit: int) -> list[int]:
    from app.models.file import FileObject

    db = get_sessionmaker()()
    try:
        return [
            int(value)
            for value in db.scalars(select(FileObject.id).where(
                FileObject.tenant_id == tenant_id,
                FileObject.is_deleted.is_(False),
                FileObject.retention_until.is_not(None),
                FileObject.retention_until <= now,
            ).order_by(FileObject.retention_until, FileObject.id).limit(max(1, min(limit, 5000)))).all()
        ]
    finally:
        db.close()


def _decision(db, row, now: datetime) -> str:
    from app.services.file_storage_governance_service import _has_active_reference

    if row.legal_hold:
        return "LEGAL_HOLD"
    if _has_active_reference(db, int(row.id), now):
        return "ACTIVE_REFERENCE"
    return "DELETE"


def _mark_pending(*, tenant_id: int, file_id: int, now: datetime) -> tuple[str, dict[str, Any]]:
    from app.models.file import FileObject

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == file_id,
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            return "MISSING", {"fileId": str(file_id), "decision": "MISSING"}
        item = {
            "fileId": str(row.id),
            "storageZone": row.storage_zone,
            "sizeBytes": int(row.size_bytes or 0),
            "objectKey": str(row.object_key or row.file_key or ""),
        }
        decision = _decision(db, row, now)
        item["decision"] = decision
        if decision == "DELETE":
            row.status = "DELETE_PENDING"
            row.updated_at = now
            db.commit()
            item["decision"] = "DELETE_PENDING"
        else:
            db.rollback()
        return decision, item
    finally:
        db.close()


def _delete_and_finalize(*, tenant_id: int, file_id: int, now: datetime) -> tuple[bool, dict[str, Any]]:
    from app.models.file import FileObject
    from app.services.storage import get_backend

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == file_id,
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            return False, {"fileId": str(file_id), "decision": "MISSING"}
        item = {
            "fileId": str(row.id),
            "storageZone": row.storage_zone,
            "sizeBytes": int(row.size_bytes or 0),
            "objectKey": str(row.object_key or row.file_key or ""),
        }
        decision = _decision(db, row, now)
        if decision != "DELETE":
            row.status = "AVAILABLE" if row.storage_zone in {"ACTIVE", "CLEAN", "ARCHIVE", "EXPORT"} else row.status
            row.updated_at = now
            db.commit()
            item["decision"] = decision
            return False, item

        key = item["objectKey"]
        backend = get_backend()
        backend.delete(key)
        if key and backend.exists(key):
            raise RuntimeError("物理对象删除后仍可被存储后端发现")
        row.is_deleted = True
        row.deleted_at = now
        row.status = "DELETED"
        row.updated_at = now
        db.commit()
        item["decision"] = "DELETED"
        return True, item
    except Exception as exc:
        db.rollback()
        fail = get_sessionmaker()()
        try:
            row = fail.scalars(select(FileObject).where(
                FileObject.id == file_id,
                FileObject.tenant_id == tenant_id,
                FileObject.is_deleted.is_(False),
            ).with_for_update()).first()
            if row:
                row.status = "DELETE_FAILED"
                row.updated_at = now
                fail.commit()
        finally:
            fail.close()
        return False, {
            "fileId": str(file_id),
            "decision": "DELETE_FAILED",
            "error": str(exc)[:1000],
        }
    finally:
        db.close()


def cleanup_expired(*, tenant_id: int, dry_run: bool = True, limit: int = 500) -> dict:
    from app.models.file import FileJob

    now = datetime.utcnow()
    job_db = get_sessionmaker()()
    try:
        job = FileJob(
            tenant_id=tenant_id,
            job_type="RETENTION_CLEANUP",
            dedupe_key=f"retention-v2:{tenant_id}:{now:%Y%m%d%H}:{uuid.uuid4().hex[:8]}",
            status="RUNNING",
            attempts=1,
            max_attempts=1,
            available_at=now,
            payload_json={"dryRun": dry_run, "limit": limit, "contractVersion": 2},
        )
        job_db.add(job)
        job_db.commit()
        job_db.refresh(job)
        job_id = int(job.id)
    finally:
        job_db.close()

    deleted = skipped_referenced = skipped_hold = failed = 0
    reclaimed = 0
    items: list[dict[str, Any]] = []
    for file_id in _candidate_ids(tenant_id=tenant_id, now=now, limit=limit):
        decision, item = _mark_pending(tenant_id=tenant_id, file_id=file_id, now=now)
        if decision == "LEGAL_HOLD":
            skipped_hold += 1
        elif decision == "ACTIVE_REFERENCE":
            skipped_referenced += 1
        elif decision == "DELETE":
            if dry_run:
                # 预演不应改变状态；恢复准备阶段的标记。
                db = get_sessionmaker()()
                try:
                    from app.models.file import FileObject
                    row = db.get(FileObject, file_id, with_for_update=True)
                    if row and row.status == "DELETE_PENDING":
                        row.status = "AVAILABLE" if row.storage_zone in {"ACTIVE", "CLEAN", "ARCHIVE", "EXPORT"} else "STORED"
                        db.commit()
                finally:
                    db.close()
                item["decision"] = "WOULD_DELETE"
            else:
                success, item = _delete_and_finalize(tenant_id=tenant_id, file_id=file_id, now=now)
                if success:
                    deleted += 1
                    reclaimed += int(item.get("sizeBytes") or 0)
                elif item.get("decision") == "LEGAL_HOLD":
                    skipped_hold += 1
                elif item.get("decision") == "ACTIVE_REFERENCE":
                    skipped_referenced += 1
                elif item.get("decision") == "DELETE_FAILED":
                    failed += 1
        items.append(item)

    result = {
        "candidateCount": len(items),
        "deleted": deleted,
        "failed": failed,
        "skippedReferenced": skipped_referenced,
        "skippedLegalHold": skipped_hold,
        "bytesReclaimed": reclaimed,
        "items": items[:200],
    }
    db = get_sessionmaker()()
    try:
        job = db.get(FileJob, job_id, with_for_update=True)
        job.status = "FAILED" if failed else "SUCCEEDED"
        job.result_json = result
        job.last_error = f"{failed} 个物理对象删除失败，等待重试" if failed else None
        db.commit()
    finally:
        db.close()
    return {"jobId": str(job_id), "dryRun": dry_run, **result}
