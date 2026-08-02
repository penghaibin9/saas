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

# ── SYS-19 bound cleanup preview/execution contract ──────────────────────────
def _candidate_snapshot(*, tenant_id: int, limit: int, now: datetime | None = None) -> dict:
    """Return a redacted, deterministic snapshot for a later one-time execution."""
    import hashlib
    import json

    from app.models.file import FileObject

    now = now or datetime.utcnow()
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(FileObject).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.is_deleted.is_(False),
            FileObject.retention_until.is_not(None),
            FileObject.retention_until <= now,
        ).order_by(FileObject.retention_until, FileObject.id).limit(max(1, min(int(limit), 5000)))).all()
        evidence = []
        items = []
        for row in rows:
            decision = _decision(db, row, now)
            evidence.append({
                "id": int(row.id),
                "version": int(row.version or 1),
                "decision": decision,
                "size": int(row.size_bytes or 0),
            })
            items.append({
                "fileId": str(row.id),
                "storageZone": row.storage_zone,
                "sizeBytes": int(row.size_bytes or 0),
                "decision": "WOULD_DELETE" if decision == "DELETE" else decision,
            })
        blob = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {
            "candidateHash": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "candidateIds": [item["id"] for item in evidence],
            "candidateCount": len(evidence),
            "items": items[:200],
            "skippedLegalHold": sum(1 for item in evidence if item["decision"] == "LEGAL_HOLD"),
            "skippedReferenced": sum(1 for item in evidence if item["decision"] == "ACTIVE_REFERENCE"),
        }
    finally:
        db.close()


def create_cleanup_preview(*, tenant_id: int, limit: int = 500, ttl_seconds: int = 600) -> dict:
    from datetime import timedelta
    from app.models.file import FileJob

    now = datetime.utcnow()
    snapshot = _candidate_snapshot(tenant_id=int(tenant_id), limit=limit, now=now)
    expires = now + timedelta(seconds=max(60, min(int(ttl_seconds), 1800)))
    db = get_sessionmaker()()
    try:
        preview_id = uuid.uuid4().hex
        row = FileJob(
            tenant_id=int(tenant_id),
            job_type="RETENTION_CLEANUP_PREVIEW",
            dedupe_key=f"cleanup-preview:{tenant_id}:{preview_id}",
            status="SUCCEEDED",
            attempts=1,
            max_attempts=1,
            available_at=now,
            payload_json={
                "previewId": preview_id,
                "candidateHash": snapshot["candidateHash"],
                "candidateIds": snapshot["candidateIds"],
                "limit": int(limit),
                "createdAt": now.isoformat(timespec="seconds"),
                "expiresAt": expires.isoformat(timespec="seconds"),
                "consumedAt": None,
                "contractVersion": 3,
            },
            result_json={k: v for k, v in snapshot.items() if k != "candidateIds"},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "previewId": preview_id,
            "previewJobId": str(row.id),
            "candidateHash": snapshot["candidateHash"],
            "expiresAt": expires.isoformat(timespec="seconds"),
            **{k: v for k, v in snapshot.items() if k not in {"candidateHash", "candidateIds"}},
        }
    finally:
        db.close()


def execute_cleanup_preview(
    *,
    tenant_id: int,
    preview_id: str,
    candidate_hash: str,
) -> dict:
    from app.core.exceptions import AppException
    from app.models.file import FileJob

    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileJob).where(
            FileJob.tenant_id == int(tenant_id),
            FileJob.job_type == "RETENTION_CLEANUP_PREVIEW",
            FileJob.dedupe_key == f"cleanup-preview:{tenant_id}:{preview_id}",
            FileJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise AppException("CLEANUP_PREVIEW_INVALID", "清理预演不存在", http_status=409)
        payload = dict(row.payload_json or {})
        if payload.get("consumedAt") or row.status == "CONSUMED":
            raise AppException("CLEANUP_PREVIEW_CONSUMED", "清理预演已使用，禁止重放", http_status=409)
        expires = datetime.fromisoformat(str(payload.get("expiresAt")))
        if expires <= now:
            raise AppException("CLEANUP_PREVIEW_EXPIRED", "清理预演已过期，请重新预演", http_status=409)
        if str(candidate_hash) != str(payload.get("candidateHash")):
            raise AppException("CLEANUP_PREVIEW_HASH_MISMATCH", "候选摘要不匹配", http_status=409)
        current = _candidate_snapshot(
            tenant_id=int(tenant_id), limit=int(payload.get("limit") or 500), now=now
        )
        if current["candidateHash"] != payload.get("candidateHash"):
            raise AppException("CLEANUP_CANDIDATES_CHANGED", "文件状态已变化，请重新预演", http_status=409)
        # Consume before physical deletion so replay remains denied even if a later
        # object deletion fails. Failed files retain DELETE_FAILED and are handled
        # by the recovery queue, never by replaying an old approval.
        payload["consumedAt"] = now.isoformat(timespec="seconds")
        row.payload_json = payload
        row.status = "CONSUMED"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    deleted = skipped_referenced = skipped_hold = failed = reclaimed = 0
    items: list[dict[str, Any]] = []
    for file_id in current["candidateIds"]:
        decision, item = _mark_pending(tenant_id=int(tenant_id), file_id=int(file_id), now=now)
        if decision == "LEGAL_HOLD":
            skipped_hold += 1
        elif decision == "ACTIVE_REFERENCE":
            skipped_referenced += 1
        elif decision == "DELETE":
            ok, item = _delete_and_finalize(tenant_id=int(tenant_id), file_id=int(file_id), now=now)
            if ok:
                deleted += 1
                reclaimed += int(item.get("sizeBytes") or 0)
            elif item.get("decision") == "DELETE_FAILED":
                failed += 1
        # Never return object keys or filenames from governance execution output.
        item.pop("objectKey", None)
        items.append(item)
    return {
        "previewId": preview_id,
        "candidateHash": candidate_hash,
        "deleted": deleted,
        "failed": failed,
        "skippedReferenced": skipped_referenced,
        "skippedLegalHold": skipped_hold,
        "bytesReclaimed": reclaimed,
        "items": items[:200],
    }
