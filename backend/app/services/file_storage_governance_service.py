"""阶段 9：文件存储治理。

权威容量来自 FileObject 实时聚合，不维护易漂移计数器；清理只处理无有效业务引用、已过保留期且
未被法律保留的对象。平台运营端仅获得容量和异常，不获得文件内容权限。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker

DEFAULT_POLICY_DAYS = {
    "QUARANTINE": 1,
    "TEMP": 1,
    "REJECTED": 7,
    "PREVIEW": 7,
    "EXPORT": 7,
    "ACTIVE": 3650,
    "CLEAN": 3650,
    "ARCHIVE": 36500,
}
_GIB = 1024 ** 3


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id(user: dict | None = None) -> int | None:
    from app.services.message_identity import resolve_message_user_id

    return resolve_message_user_id(user or get_current_user_ctx() or {}) or None


def _module_from_biz(biz_type: str | None) -> str:
    value = str(biz_type or "").upper()
    for prefix, module in (
        ("GRADUATION", "GRADUATION"),
        ("INTERNSHIP", "INTERNSHIP"),
        ("AFFAIRS", "STUDENT_AFFAIRS"),
        ("ACADEMIC", "ACADEMIC_AFFAIRS"),
        ("IDENTITY", "SYSTEM"),
        ("MIGRATION", "SYSTEM"),
        ("DATA_EXCHANGE", "SYSTEM"),
    ):
        if value.startswith(prefix):
            return module
    return "SHARED"


def _default_retention_days(storage_zone: str | None, biz_type: str | None) -> int:
    zone = str(storage_zone or "ACTIVE").upper()
    biz = str(biz_type or "").upper()
    if "ARCHIVE" in biz or zone == "ARCHIVE":
        return DEFAULT_POLICY_DAYS["ARCHIVE"]
    if "EXPORT" in biz or "RECEIPT" in biz or zone == "EXPORT":
        return DEFAULT_POLICY_DAYS["EXPORT"]
    return DEFAULT_POLICY_DAYS.get(zone, DEFAULT_POLICY_DAYS["ACTIVE"])


def effective_retention_days(
    *,
    tenant_id: int,
    module_code: str | None,
    biz_type: str | None,
    storage_zone: str | None,
    db,
) -> int:
    from app.models.file import FileRetentionPolicy

    policies = db.scalars(select(FileRetentionPolicy).where(
        FileRetentionPolicy.tenant_id == tenant_id,
        FileRetentionPolicy.is_deleted.is_(False),
        FileRetentionPolicy.is_active.is_(True),
        or_(FileRetentionPolicy.module_code.is_(None), FileRetentionPolicy.module_code == module_code),
        or_(FileRetentionPolicy.biz_type.is_(None), FileRetentionPolicy.biz_type == biz_type),
        or_(FileRetentionPolicy.storage_zone.is_(None), FileRetentionPolicy.storage_zone == storage_zone),
    ).order_by(FileRetentionPolicy.priority.asc(), FileRetentionPolicy.id.asc())).all()
    if policies:
        return max(0, int(policies[0].retention_days or 0))
    return _default_retention_days(storage_zone, biz_type)


def assign_retention(file_obj, *, module_code: str | None = None, db=None, force: bool = False) -> datetime | None:
    """为新文件或历史空值文件计算保留截止；法律保留只阻止清理，不篡改原政策日期。"""
    owns = db is None
    working = db or get_sessionmaker()()
    try:
        if file_obj.retention_until and not force:
            return file_obj.retention_until
        days = effective_retention_days(
            tenant_id=int(file_obj.tenant_id),
            module_code=module_code or _module_from_biz(file_obj.biz_type),
            biz_type=file_obj.biz_type,
            storage_zone=file_obj.storage_zone,
            db=working,
        )
        base = file_obj.available_at or file_obj.created_at or datetime.utcnow()
        file_obj.retention_until = base + timedelta(days=days)
        if owns:
            working.add(file_obj)
            working.commit()
        return file_obj.retention_until
    finally:
        if owns:
            working.close()


def backfill_retention(*, tenant_id: int, limit: int = 500) -> dict:
    from app.models.file import FileObject

    db = get_sessionmaker()()
    updated = 0
    try:
        rows = db.scalars(select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
            FileObject.retention_until.is_(None),
        ).order_by(FileObject.id).limit(max(1, min(limit, 5000))).with_for_update()).all()
        for row in rows:
            assign_retention(row, db=db)
            updated += 1
        db.commit()
        return {"tenantId": tenant_id, "updated": updated}
    finally:
        db.close()


def _quota_row(db, tenant_id: int):
    from app.models.file import TenantStorageQuota

    return db.scalars(select(TenantStorageQuota).where(
        TenantStorageQuota.tenant_id == tenant_id,
        TenantStorageQuota.is_deleted.is_(False),
    )).first()


def usage_snapshot(*, tenant_id: int | None = None) -> dict:
    from app.models.file import FileObject

    tenant_id = _tenant_id(tenant_id)
    db = get_sessionmaker()()
    try:
        base = (
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        )
        total_bytes, total_files = db.execute(select(
            func.coalesce(func.sum(FileObject.size_bytes), 0),
            func.count(FileObject.id),
        ).where(*base)).one()
        by_zone = [
            {"storageZone": zone or "UNKNOWN", "bytes": int(size or 0), "files": int(count or 0)}
            for zone, size, count in db.execute(select(
                FileObject.storage_zone,
                func.coalesce(func.sum(FileObject.size_bytes), 0),
                func.count(FileObject.id),
            ).where(*base).group_by(FileObject.storage_zone)).all()
        ]
        by_module = [
            {"moduleCode": _module_from_biz(biz), "bizType": biz or "UNKNOWN", "bytes": int(size or 0), "files": int(count or 0)}
            for biz, size, count in db.execute(select(
                FileObject.biz_type,
                func.coalesce(func.sum(FileObject.size_bytes), 0),
                func.count(FileObject.id),
            ).where(*base).group_by(FileObject.biz_type)).all()
        ]
        quota = _quota_row(db, tenant_id)
        quota_bytes = int(quota.total_quota_bytes) if quota else None
        used = int(total_bytes or 0)
        usage_percent = round(used * 100 / quota_bytes, 2) if quota_bytes else None
        since = datetime.utcnow() - timedelta(days=30)
        recent_bytes = int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
            *base,
            FileObject.created_at >= since,
        )) or 0)
        return {
            "tenantId": tenant_id,
            "totalBytes": used,
            "totalGiB": round(used / _GIB, 3),
            "totalFiles": int(total_files or 0),
            "quotaBytes": quota_bytes,
            "quotaGiB": round(quota_bytes / _GIB, 3) if quota_bytes else None,
            "usagePercent": usage_percent,
            "warningPercent": int(quota.warning_percent) if quota else None,
            "hardLimitEnabled": bool(quota.hard_limit_enabled) if quota else False,
            "quotaVersion": int(quota.version) if quota else 0,
            "moduleQuotaBytes": dict(quota.module_quota_json or {}) if quota else {},
            "estimatedNext30DaysGrowthBytes": recent_bytes,
            "estimatedNext30DaysTotalBytes": used + recent_bytes,
            "byZone": by_zone,
            "byBizType": by_module,
        }
    finally:
        db.close()


def assert_quota_available(size_bytes: int, *, tenant_id: int | None = None, module_code: str | None = None) -> dict:
    tenant_id = _tenant_id(tenant_id)
    requested = max(0, int(size_bytes or 0))
    snapshot = usage_snapshot(tenant_id=tenant_id)
    db = get_sessionmaker()()
    try:
        quota = _quota_row(db, tenant_id)
        if not quota:
            return {**snapshot, "allowed": True, "reason": "NO_QUOTA_CONFIGURED"}
        total_limit = int(quota.total_quota_bytes or 0)
        if quota.hard_limit_enabled and total_limit > 0 and snapshot["totalBytes"] + requested > total_limit:
            raise AppException(
                "TENANT_STORAGE_QUOTA_EXCEEDED",
                "学校文件存储空间已满，请清理过期文件或联系学校管理员扩容",
                http_status=409,
                details={"usedBytes": snapshot["totalBytes"], "quotaBytes": total_limit, "requestedBytes": requested},
            )
        module_limits = dict(quota.module_quota_json or {})
        module_limit = int(module_limits.get(str(module_code or "").upper()) or 0)
        if quota.hard_limit_enabled and module_limit > 0:
            module_used = sum(
                int(item["bytes"] or 0)
                for item in snapshot["byBizType"]
                if item["moduleCode"] == str(module_code or "").upper()
            )
            if module_used + requested > module_limit:
                raise AppException(
                    "MODULE_STORAGE_QUOTA_EXCEEDED",
                    "当前业务模块存储空间已满",
                    http_status=409,
                    details={"moduleCode": module_code, "usedBytes": module_used, "quotaBytes": module_limit, "requestedBytes": requested},
                )
        return {**snapshot, "allowed": True}
    finally:
        db.close()


def upsert_quota(
    *,
    total_quota_bytes: int,
    warning_percent: int,
    hard_limit_enabled: bool,
    module_quota_json: dict | None,
    description: str | None,
    user: dict,
    expected_version: int | None = None,
) -> dict:
    from app.models.file import TenantStorageQuota

    tenant_id = _tenant_id()
    if int(total_quota_bytes or 0) <= 0:
        raise AppException("VALIDATION_ERROR", "租户总配额必须大于 0")
    if not 1 <= int(warning_percent or 0) <= 100:
        raise AppException("VALIDATION_ERROR", "预警百分比必须为 1-100")
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        row = _quota_row(db, tenant_id)
        current_version = int(row.version) if row else 0
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException(
                "DATA_CONFLICT", "存储配额已被其他操作更新，请刷新后重试",
                http_status=409,
                details={"expectedVersion": expected_version, "currentVersion": current_version},
            )
        module_limits = {str(k).upper(): int(v or 0) for k, v in dict(module_quota_json or {}).items()}
        if any(value < 0 for value in module_limits.values()):
            raise AppException("VALIDATION_ERROR", "模块配额不能为负数")
        if sum(module_limits.values()) > int(total_quota_bytes):
            raise AppException("VALIDATION_ERROR", "模块配额合计不能超过学校总配额")
        from app.services.entitlement_reconciliation_service import commercial_storage_limit_bytes
        commercial_limit = commercial_storage_limit_bytes(tenant_id)
        if commercial_limit and int(total_quota_bytes) > commercial_limit:
            raise AppException(
                "SCHOOL_QUOTA_EXCEEDS_COMMERCIAL",
                "学校治理配额不能超过平台商业授权上限",
                http_status=409,
                details={"commercialLimitBytes": commercial_limit, "requestedBytes": int(total_quota_bytes)},
            )
        if not row:
            row = TenantStorageQuota(tenant_id=tenant_id, created_by=actor_id)
            db.add(row)
        else:
            row.version = current_version + 1
        row.total_quota_bytes = int(total_quota_bytes)
        row.warning_percent = int(warning_percent)
        row.hard_limit_enabled = bool(hard_limit_enabled)
        row.module_quota_json = module_limits
        row.description = str(description or "")[:500] or None
        row.updated_by = actor_id
        db.commit()
        db.refresh(row)
        return usage_snapshot(tenant_id=tenant_id)
    finally:
        db.close()


def list_policies(*, tenant_id: int | None = None) -> list[dict]:
    from app.models.file import FileRetentionPolicy

    tenant_id = _tenant_id(tenant_id)
    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(FileRetentionPolicy).where(
            FileRetentionPolicy.tenant_id == tenant_id,
            FileRetentionPolicy.is_deleted.is_(False),
        ).order_by(FileRetentionPolicy.priority, FileRetentionPolicy.id)).all()
        return [{
            "id": str(row.id),
            "policyCode": row.policy_code,
            "moduleCode": row.module_code,
            "bizType": row.biz_type,
            "storageZone": row.storage_zone,
            "retentionDays": row.retention_days,
            "cleanupAction": row.cleanup_action,
            "priority": row.priority,
            "active": row.is_active,
            "description": row.description,
            "version": row.version,
        } for row in rows]
    finally:
        db.close()


def upsert_policy(data: dict, *, user: dict, expected_version: int | None = None) -> dict:
    from app.models.file import FileRetentionPolicy

    tenant_id = _tenant_id()
    code = str(data.get("policyCode") or "").strip().upper()
    if not code:
        raise AppException("VALIDATION_ERROR", "policyCode 必填")
    days = int(data.get("retentionDays") or 0)
    if days < 0 or days > 36500:
        raise AppException("VALIDATION_ERROR", "保留天数必须为 0-36500")
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileRetentionPolicy).where(
            FileRetentionPolicy.tenant_id == tenant_id,
            FileRetentionPolicy.policy_code == code,
            FileRetentionPolicy.is_deleted.is_(False),
        ).with_for_update()).first()
        current_version = int(row.version) if row else 0
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "保留策略已更新，请刷新后重试", http_status=409)
        if not row:
            row = FileRetentionPolicy(tenant_id=tenant_id, policy_code=code, created_by=actor_id)
            db.add(row)
        else:
            row.version = current_version + 1
        row.module_code = str(data.get("moduleCode") or "").upper() or None
        row.biz_type = str(data.get("bizType") or "").upper() or None
        row.storage_zone = str(data.get("storageZone") or "").upper() or None
        row.retention_days = days
        row.cleanup_action = str(data.get("cleanupAction") or "DELETE_BYTES").upper()
        row.priority = int(data.get("priority") or 100)
        row.is_active = bool(data.get("active", True))
        row.description = str(data.get("description") or "")[:500] or None
        row.updated_by = actor_id
        db.commit()
        db.refresh(row)
        return next(item for item in list_policies(tenant_id=tenant_id) if item["id"] == str(row.id))
    finally:
        db.close()


def set_legal_hold(file_id: str, *, enabled: bool, reason: str, user: dict, expected_version: int | None = None) -> dict:
    from app.models.file import FileObject
    from app.services import audit_log

    tenant_id = _tenant_id()
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id),
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("文件不存在")
        if expected_version is not None and int(expected_version) != int(row.version or 1):
            raise AppException("DATA_CONFLICT", "法律保留状态已更新，请刷新后重试", http_status=409)
        row.legal_hold = bool(enabled)
        row.version = int(row.version or 1) + 1
        row.updated_by = _actor_id(user)
        db.commit()
        audit_log.record(
            "FILE_LEGAL_HOLD_SET" if enabled else "FILE_LEGAL_HOLD_RELEASED",
            f"file:{file_id}",
            detail={"reason": str(reason or "")[:500]},
        )
        return {"fileId": str(file_id), "legalHold": row.legal_hold, "retentionUntil": row.retention_until.isoformat() if row.retention_until else None, "version": int(row.version or 1)}
    finally:
        db.close()


def _has_active_reference(db, file_id: int, now: datetime) -> bool:
    from app.models.data_exchange import ExportJob
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileVersion

    if db.scalar(select(func.count(FileBinding.id)).where(
        FileBinding.file_id == file_id,
        FileBinding.is_deleted.is_(False),
        FileBinding.is_current.is_(True),
        FileBinding.status == "ACTIVE",
    )):
        return True
    if db.scalar(select(func.count(FileVersion.id)).where(
        FileVersion.file_object_id == file_id,
        FileVersion.is_deleted.is_(False),
        FileVersion.is_current.is_(True),
        FileVersion.status.notin_(["INVALIDATED", "REJECTED"]),
    )):
        return True
    if db.scalar(select(func.count(ArchiveManifestItem.id)).join(
        ArchiveManifest, ArchiveManifest.id == ArchiveManifestItem.manifest_id,
    ).where(
        ArchiveManifestItem.file_object_id == file_id,
        ArchiveManifestItem.is_deleted.is_(False),
        ArchiveManifest.is_deleted.is_(False),
        ArchiveManifest.status.notin_(["REVOKED", "SUPERSEDED", "ABORTED"]),
    )):
        return True
    export = db.scalars(select(ExportJob).where(
        ExportJob.file_object_id == file_id,
        ExportJob.is_deleted.is_(False),
    ).order_by(ExportJob.id.desc())).first()
    if export and export.status == "SUCCEEDED" and not export.revoked_at and (not export.expires_at or export.expires_at > now):
        return True
    return False


def cleanup_expired(*, tenant_id: int, dry_run: bool = True, limit: int = 500) -> dict:
    from app.models.file import FileJob, FileObject
    from app.services.storage import get_backend

    now = datetime.utcnow()
    db = get_sessionmaker()()
    job = FileJob(
        tenant_id=tenant_id,
        job_type="RETENTION_CLEANUP",
        dedupe_key=f"retention:{tenant_id}:{now:%Y%m%d%H}:{uuid.uuid4().hex[:8]}",
        status="RUNNING",
        attempts=1,
        max_attempts=1,
        available_at=now,
        payload_json={"dryRun": dry_run, "limit": limit},
    )
    deleted = skipped_referenced = skipped_hold = 0
    reclaimed = 0
    candidates: list[dict[str, Any]] = []
    try:
        db.add(job)
        db.flush()
        rows = db.scalars(select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.is_deleted.is_(False),
            FileObject.retention_until.is_not(None),
            FileObject.retention_until <= now,
        ).order_by(FileObject.retention_until, FileObject.id).limit(max(1, min(limit, 5000))).with_for_update()).all()
        backend = get_backend()
        for row in rows:
            item = {"fileId": str(row.id), "storageZone": row.storage_zone, "sizeBytes": int(row.size_bytes or 0)}
            if row.legal_hold:
                skipped_hold += 1
                item["decision"] = "LEGAL_HOLD"
            elif _has_active_reference(db, row.id, now):
                skipped_referenced += 1
                item["decision"] = "ACTIVE_REFERENCE"
            else:
                item["decision"] = "DELETE" if not dry_run else "WOULD_DELETE"
                if not dry_run:
                    backend.delete(str(row.object_key or row.file_key))
                    row.is_deleted = True
                    row.deleted_at = now
                    row.status = "DELETED"
                    row.updated_at = now
                    deleted += 1
                    reclaimed += int(row.size_bytes or 0)
            candidates.append(item)
        job.status = "SUCCEEDED"
        job.result_json = {
            "candidateCount": len(rows),
            "deleted": deleted,
            "skippedReferenced": skipped_referenced,
            "skippedLegalHold": skipped_hold,
            "bytesReclaimed": reclaimed,
            "items": candidates[:200],
        }
        db.commit()
        return {"jobId": str(job.id), "dryRun": dry_run, **job.result_json}
    except Exception as exc:
        db.rollback()
        fail = get_sessionmaker()()
        try:
            failed = fail.get(FileJob, job.id) if job.id else None
            if failed:
                failed.status = "FAILED"
                failed.last_error = str(exc)[:2000]
                fail.commit()
        finally:
            fail.close()
        raise
    finally:
        db.close()


def anomaly_snapshot(*, tenant_id: int | None = None) -> dict:
    from app.models.file import FileBinding, FileObject

    tenant_id = _tenant_id(tenant_id)
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        base = (FileObject.tenant_id == tenant_id, FileObject.is_deleted.is_(False))
        orphan_count = int(db.scalar(select(func.count(FileObject.id)).where(
            *base,
            FileObject.created_at < now - timedelta(hours=24),
            ~select(FileBinding.id).where(
                FileBinding.file_id == FileObject.id,
                FileBinding.is_deleted.is_(False),
                FileBinding.is_current.is_(True),
            ).exists(),
        )) or 0)
        return {
            "tenantId": tenant_id,
            "quarantineOverOneHour": int(db.scalar(select(func.count(FileObject.id)).where(
                *base, FileObject.storage_zone == "QUARANTINE", FileObject.created_at < now - timedelta(hours=1),
            )) or 0),
            "scanErrors": int(db.scalar(select(func.count(FileObject.id)).where(
                *base, FileObject.scan_status == "ERROR",
            )) or 0),
            "expiredPendingCleanup": int(db.scalar(select(func.count(FileObject.id)).where(
                *base, FileObject.legal_hold.is_(False), FileObject.retention_until <= now,
            )) or 0),
            "cosUnverified": int(db.scalar(select(func.count(FileObject.id)).where(
                *base, FileObject.storage_backend == "cos", FileObject.storage_verified_at.is_(None),
            )) or 0),
            "unboundOver24Hours": orphan_count,
            "legalHoldFiles": int(db.scalar(select(func.count(FileObject.id)).where(
                *base, FileObject.legal_hold.is_(True),
            )) or 0),
        }
    finally:
        db.close()


def governance_overview(*, tenant_id: int | None = None) -> dict:
    tenant_id = _tenant_id(tenant_id)
    return {
        "usage": usage_snapshot(tenant_id=tenant_id),
        "anomalies": anomaly_snapshot(tenant_id=tenant_id),
        "policies": list_policies(tenant_id=tenant_id),
        "defaultPolicies": DEFAULT_POLICY_DAYS,
    }


def operational_health(*, tenant_id: int | None = None) -> dict:
    """Operational signals only; no filenames, object keys or content metadata."""
    from app.models.file import FileJob, FileObject
    from app.models.file_quota import FileStorageQuotaReservation

    tenant_id = _tenant_id(tenant_id)
    now = datetime.utcnow()
    db = get_sessionmaker()()
    try:
        return {
            "tenantId": tenant_id,
            "scanBacklog": int(db.scalar(select(func.count(FileObject.id)).where(
                FileObject.tenant_id == tenant_id,
                FileObject.is_deleted.is_(False),
                FileObject.scan_status.in_(("PENDING", "PROCESSING")),
            )) or 0),
            "failedFileJobs": int(db.scalar(select(func.count(FileJob.id)).where(
                FileJob.tenant_id == tenant_id,
                FileJob.is_deleted.is_(False),
                FileJob.status == "FAILED",
            )) or 0),
            "heldReservations": int(db.scalar(select(func.count(FileStorageQuotaReservation.id)).where(
                FileStorageQuotaReservation.tenant_id == tenant_id,
                FileStorageQuotaReservation.is_deleted.is_(False),
                FileStorageQuotaReservation.status == "HELD",
                FileStorageQuotaReservation.expires_at > now,
            )) or 0),
            "expiredHeldReservations": int(db.scalar(select(func.count(FileStorageQuotaReservation.id)).where(
                FileStorageQuotaReservation.tenant_id == tenant_id,
                FileStorageQuotaReservation.is_deleted.is_(False),
                FileStorageQuotaReservation.status == "HELD",
                FileStorageQuotaReservation.expires_at <= now,
            )) or 0),
            "cleanupPreviewContract": "BOUND_ONE_TIME_V3",
        }
    finally:
        db.close()
