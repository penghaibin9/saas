"""Idempotent tenant physical purge executor.

Business/config rows are hard-deleted in reverse metadata dependency order.
FileObject bytes are deleted only through the existing storage-governance
cleanup path; metadata is hard-deleted only after the backend confirms the
physical object no longer exists.  Retained compliance rows are counted but not
removed.  Any unknown registry table or failed file deletion blocks PURGED.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import delete, func, select, update

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services.tenant_purge_registry import (
    FILE_OBJECT,
    PURGE,
    RETAIN,
    REGISTRY_VERSION,
    assert_registry_complete,
    classify_table,
)

_BATCH = 1000


def _count(db, table, tenant_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(table).where(table.c.tenant_id == int(tenant_id))) or 0)


def _hard_delete_table(db, table, tenant_id: int, *, batch_size: int = _BATCH) -> int:
    if "id" not in table.c:
        raise AppException(
            "TENANT_PURGE_UNBOUNDED_TABLE",
            f"租户表 {table.name} 没有 id，拒绝无界物理删除",
            http_status=409,
        )
    total = 0
    while True:
        ids = list(db.scalars(select(table.c.id).where(
            table.c.tenant_id == int(tenant_id)
        ).order_by(table.c.id).limit(max(1, min(int(batch_size), 5000)))).all())
        if not ids:
            break
        result = db.execute(delete(table).where(
            table.c.tenant_id == int(tenant_id), table.c.id.in_(ids)
        ))
        total += int(result.rowcount or len(ids))
        db.commit()
    return total


def _purge_file_objects(tenant_id: int) -> dict:
    from app.models.file import FileObject
    from app.services import file_storage_cleanup_service as cleanup

    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        legal_hold = int(db.scalar(select(func.count(FileObject.id)).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.is_deleted.is_(False),
            FileObject.legal_hold.is_(True),
        )) or 0)
        if legal_hold:
            raise AppException(
                "TENANT_PURGE_LEGAL_HOLD",
                "仍有文件处于 Legal Hold，禁止物理销毁",
                http_status=409,
                details={"legalHoldFileCount": legal_hold},
            )
        # Offboarding retention has already elapsed/been approved.  Set the
        # cleanup eligibility date; the cleanup service still rechecks legal
        # hold + active business references under row locks.
        db.execute(update(FileObject).where(
            FileObject.tenant_id == int(tenant_id),
            FileObject.is_deleted.is_(False),
        ).values(retention_until=now))
        db.commit()
    finally:
        db.close()

    deleted = failed = skipped = bytes_reclaimed = 0
    while True:
        ids = cleanup._candidate_ids(tenant_id=int(tenant_id), now=now, limit=500)
        if not ids:
            break
        progressed = 0
        for file_id in ids:
            decision, _ = cleanup._mark_pending(tenant_id=int(tenant_id), file_id=int(file_id), now=now)
            if decision == "LEGAL_HOLD":
                raise AppException("TENANT_PURGE_LEGAL_HOLD", "销毁期间出现新的 Legal Hold，已停止", http_status=409)
            if decision == "ACTIVE_REFERENCE":
                skipped += 1
                continue
            if decision != "DELETE":
                continue
            ok, item = cleanup._delete_and_finalize(tenant_id=int(tenant_id), file_id=int(file_id), now=now)
            if ok:
                deleted += 1
                bytes_reclaimed += int(item.get("sizeBytes") or 0)
                progressed += 1
            elif item.get("decision") == "DELETE_FAILED":
                failed += 1
        if failed or skipped:
            break
        if progressed == 0:
            break

    db = get_sessionmaker()()
    try:
        remaining_active = int(db.scalar(select(func.count(FileObject.id)).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False)
        )) or 0)
        if remaining_active or failed or skipped:
            raise AppException(
                "TENANT_PURGE_FILE_INCOMPLETE",
                "文件物理销毁未完全成功，拒绝标记租户已销毁",
                http_status=409,
                details={
                    "remainingActive": remaining_active,
                    "failed": failed,
                    "activeReferenceBlocked": skipped,
                },
            )
        # Physical bytes are already proven absent by cleanup._delete_and_finalize.
        # Hard-delete the now-tombstoned metadata to avoid retaining filenames,
        # object keys or other business metadata after tenant destruction.
        metadata_deleted = _hard_delete_table(db, FileObject.__table__, int(tenant_id))
        return {
            "deletedFileCount": deleted,
            "deletedFileMetadataCount": metadata_deleted,
            "deletedBytes": bytes_reclaimed,
        }
    finally:
        db.close()


def execute_tenant_purge(tenant_id: int, *, source_commit: str | None = None) -> dict:
    registry = assert_registry_complete()
    from app.db.base import metadata

    deleted_rows: dict[str, int] = {}
    retained_rows: dict[str, int] = {}

    # Reverse topological table order minimizes FK conflicts.  FileObject is a
    # special terminal phase because storage bytes must be verified absent first.
    for table in reversed(metadata.sorted_tables):
        if "tenant_id" not in table.c:
            continue
        item = classify_table(table.name)
        if item.classification == FILE_OBJECT:
            continue
        db = get_sessionmaker()()
        try:
            if item.classification == RETAIN:
                retained_rows[table.name] = _count(db, table, int(tenant_id))
                continue
            if item.classification != PURGE:
                raise AppException(
                    "TENANT_PURGE_REGISTRY_INCOMPLETE",
                    f"未分类租户表：{table.name}", http_status=409,
                )
            deleted_rows[table.name] = _hard_delete_table(db, table, int(tenant_id))
        finally:
            db.close()

    file_result = _purge_file_objects(int(tenant_id))

    # Final proof: every PURGE/FILE_OBJECT table must contain zero tenant rows.
    residual: dict[str, int] = {}
    db = get_sessionmaker()()
    try:
        for table in metadata.sorted_tables:
            if "tenant_id" not in table.c:
                continue
            classification = classify_table(table.name).classification
            if classification not in {PURGE, FILE_OBJECT}:
                continue
            count = _count(db, table, int(tenant_id))
            if count:
                residual[table.name] = count
    finally:
        db.close()
    if residual:
        raise AppException(
            "TENANT_PURGE_RESIDUAL_DATA",
            "租户销毁后仍检测到业务数据残留",
            http_status=409,
            details={"residualTables": residual},
        )

    evidence = {
        "schemaVersion": 1,
        "tenantId": str(int(tenant_id)),
        "registryVersion": REGISTRY_VERSION,
        "sourceCommit": str(source_commit or "unknown"),
        "deletedTableCount": sum(1 for count in deleted_rows.values() if count > 0),
        "deletedRowCount": sum(deleted_rows.values()),
        "retainedEvidenceCount": sum(retained_rows.values()),
        "retainedTables": retained_rows,
        **file_result,
        "failedCount": 0,
        "completedAt": datetime.utcnow().isoformat(timespec="seconds"),
    }
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    evidence["evidenceSha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"registry": registry, "deletedRows": deleted_rows, "evidence": evidence}
