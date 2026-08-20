"""Tenant offboarding → retention → governed destruction authority."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.tenant_offboarding import TenantOffboardingJob, TenantOffboardingStep, TenantTombstone

ACTIVE_STATES = {"REQUESTED", "PRECHECK", "FROZEN_READONLY", "FINAL_EXPORT_READY", "RETENTION", "PURGE_READY", "PURGING"}
CANCELLABLE_STATES = {"REQUESTED", "PRECHECK", "FROZEN_READONLY", "FINAL_EXPORT_READY", "RETENTION"}


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "")
    raw = raw.removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def _session():
    return get_sessionmaker()()


def _meta_row(db, tenant_id: int, *, lock: bool = False, create: bool = False):
    from app.models import PlatformConfig

    q = select(PlatformConfig).where(
        PlatformConfig.tenant_id == int(tenant_id),
        PlatformConfig.config_type == "TENANT_META",
        PlatformConfig.config_key == "-",
        PlatformConfig.is_deleted.is_(False),
    )
    if lock:
        q = q.with_for_update()
    row = db.scalars(q).first()
    if row is None and create:
        row = PlatformConfig(tenant_id=int(tenant_id), config_type="TENANT_META", config_key="-", config_json={}, enabled=True)
        db.add(row)
        db.flush()
    return row


def _version(tenant, meta) -> int:
    return max(int(getattr(tenant, "version", 0) or 0), int(getattr(meta, "version", 0) or 0))


def _set_step(db, job_id: int, code: str, status: str, *, result: dict | None = None, error: str | None = None) -> None:
    row = db.scalars(select(TenantOffboardingStep).where(
        TenantOffboardingStep.job_id == int(job_id),
        TenantOffboardingStep.step_code == code,
        TenantOffboardingStep.is_deleted.is_(False),
    ).with_for_update()).first()
    now = datetime.utcnow()
    if row is None:
        row = TenantOffboardingStep(job_id=int(job_id), step_code=code, status=status, attempts=0)
        db.add(row)
    row.status = status
    row.attempts = int(row.attempts or 0) + (1 if status == "RUNNING" else 0)
    row.result_json = dict(result or row.result_json or {})
    row.last_error = error
    if status == "RUNNING":
        row.started_at = now
    if status in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}:
        row.finished_at = now


def _revoke_refresh_by_tenant(db, tenant_id: int) -> int:
    from app.models import AuthRefreshToken, User

    user_ids = [f"db-{int(uid)}" for uid in db.scalars(select(User.id).where(
        User.tenant_id == int(tenant_id), User.is_deleted.is_(False)
    )).all()]
    deleted_count = 0
    for start in range(0, len(user_ids), 500):
        batch = user_ids[start:start + 500]
        if not batch:
            continue
        result = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id.in_(batch)))
        deleted_count += int(result.rowcount or 0)
    return deleted_count


def _basic_counts(db, tenant_id: int) -> dict:
    from app.models import StudentProfile, User
    from app.models.file import FileJob, FileObject

    return {
        "studentCount": int(db.scalar(select(func.count(StudentProfile.id)).where(
            StudentProfile.tenant_id == int(tenant_id), StudentProfile.is_deleted.is_(False)
        )) or 0),
        "userCount": int(db.scalar(select(func.count(User.id)).where(
            User.tenant_id == int(tenant_id), User.is_deleted.is_(False)
        )) or 0),
        "fileCount": int(db.scalar(select(func.count(FileObject.id)).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False)
        )) or 0),
        "fileBytes": int(db.scalar(select(func.coalesce(func.sum(FileObject.size_bytes), 0)).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False)
        )) or 0),
        "legalHoldFileCount": int(db.scalar(select(func.count(FileObject.id)).where(
            FileObject.tenant_id == int(tenant_id), FileObject.is_deleted.is_(False), FileObject.legal_hold.is_(True)
        )) or 0),
        "activeFileJobCount": int(db.scalar(select(func.count(FileJob.id)).where(
            FileJob.tenant_id == int(tenant_id), FileJob.is_deleted.is_(False),
            FileJob.status.in_(("PENDING", "RUNNING"))
        )) or 0),
    }


def preview_offboarding(tenant_id: int) -> dict:
    from app.models import Tenant
    from app.services.tenant_effective_state_service import get_effective_state
    from app.services.tenant_purge_registry import inventory

    db = _session()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None or tenant.is_deleted:
            raise not_found("租户不存在")
        state = get_effective_state(int(tenant_id), strict=True, db=db)
        counts = _basic_counts(db, int(tenant_id))
        registry = inventory()
        active_job = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.tenant_id == int(tenant_id),
            TenantOffboardingJob.state.in_(tuple(ACTIVE_STATES)),
            TenantOffboardingJob.is_deleted.is_(False),
        ).order_by(TenantOffboardingJob.id.desc())).first()
        blockers = []
        if counts["legalHoldFileCount"]:
            blockers.append({"code": "LEGAL_HOLD", "message": "存在文件 Legal Hold；允许冻结，但禁止物理销毁"})
        if not registry["complete"]:
            blockers.append({"code": "PURGE_REGISTRY_INCOMPLETE", "message": "存在未分类 tenant_id 表，禁止物理销毁", "tables": registry["unknownTables"]})
        if counts["activeFileJobCount"]:
            blockers.append({"code": "ACTIVE_FILE_JOBS", "message": "仍有文件任务运行；冻结后需等待/收敛"})
        return {
            "tenantId": str(tenant.id), "tenantCode": tenant.tenant_code, "tenantName": tenant.school_name,
            "effectiveState": state, "counts": counts,
            "registry": {k: registry[k] for k in ("registryVersion", "complete", "unknownTables", "purgeTableCount", "retainTableCount")},
            "activeJobId": str(active_job.id) if active_job else None,
            "blockers": blockers,
            "warnings": [
                "发起后租户立即进入 readonly，普通交互式登录与业务写入将被拒绝",
                "最终导出 SHA256 未确认前不能进入保留/销毁",
                "PURGE_READY 之后不可恢复，失败只能幂等续跑",
            ],
        }
    finally:
        db.close()


def request_offboarding(user: dict, tenant_id: int, *, reason: str, expected_version: int, retention_days: int = 30) -> dict:
    from app.models import Tenant
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    reason = str(reason or "").strip()
    if len(reason) < 10:
        raise AppException("VALIDATION_ERROR", "退租原因至少10个字符")
    preview = preview_offboarding(int(tenant_id))
    db = _session()
    try:
        tenant = db.scalars(select(Tenant).where(Tenant.id == int(tenant_id), Tenant.is_deleted.is_(False)).with_for_update()).first()
        if tenant is None:
            raise not_found("租户不存在")
        meta = _meta_row(db, int(tenant_id), lock=True, create=True)
        current_version = _version(tenant, meta)
        if int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "租户状态已变化，请刷新后重试", http_status=409,
                               details={"expectedVersion": expected_version, "currentVersion": current_version})
        existing = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.tenant_id == int(tenant_id),
            TenantOffboardingJob.state.in_(tuple(ACTIVE_STATES)),
            TenantOffboardingJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if existing is not None:
            raise AppException("DATA_CONFLICT", "该租户已有未结束退租任务", http_status=409,
                               details={"jobId": str(existing.id), "state": existing.state})
        meta_payload = dict(meta.config_json or {})
        requested_days = int(retention_days)
        environment = str(meta_payload.get("environment") or "production").lower()
        sandbox_like = environment != "production" or str(tenant.tenant_code).lower().startswith(("sandbox", "test", "demo"))
        if requested_days < 1 and not sandbox_like:
            raise AppException("VALIDATION_ERROR", "生产租户保留期至少1天")
        retention_until = datetime.utcnow() + timedelta(days=max(0, requested_days))
        before = {
            "rowStatus": tenant.status,
            "metaStatus": meta_payload.get("status"),
            "tenantVersion": int(tenant.version or 0),
            "metaVersion": int(meta.version or 0),
        }
        job = TenantOffboardingJob(
            tenant_id=int(tenant_id), state="PRECHECK", reason=reason,
            requested_by=_actor_id(user), expected_tenant_version=current_version,
            retention_until=retention_until, legal_hold_blocked=bool(preview["counts"]["legalHoldFileCount"]),
            preview_json={**preview, "beforeState": before}, requested_at=datetime.utcnow(),
        )
        db.add(job)
        db.flush()
        _set_step(db, job.id, "PRECHECK", "SUCCEEDED", result=preview)

        # Freeze business writes using the existing canonical effective-state
        # semantics.  Platform-side export/offboarding operations remain possible.
        tenant.status = "ACTIVE"
        meta_payload["status"] = "readonly"
        meta.config_json = meta_payload
        tenant.version = int(tenant.version or 0) + 1
        meta.version = int(meta.version or 0) + 1
        revoked = _revoke_refresh_by_tenant(db, int(tenant_id))
        job.state = "FROZEN_READONLY"
        _set_step(db, job.id, "FREEZE", "SUCCEEDED", result={"refreshTokensRevoked": revoked})
        db.commit()
        db.refresh(job)
    finally:
        db.close()
    invalidate_tenant_subject_caches(int(tenant_id))
    return get_job(int(job.id))


def confirm_final_export(user: dict, job_id: int, *, sha256: str) -> dict:
    from app.models import Tenant
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    digest = str(sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise AppException("VALIDATION_ERROR", "finalExportSha256 必须是64位 SHA256")
    db = _session()
    try:
        job = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.id == int(job_id), TenantOffboardingJob.is_deleted.is_(False)
        ).with_for_update()).first()
        if job is None:
            raise not_found("退租任务不存在")
        if job.state not in {"FROZEN_READONLY", "FINAL_EXPORT_READY"}:
            raise AppException("DATA_CONFLICT", f"当前状态 {job.state} 不能确认最终导出", http_status=409)
        tenant = db.get(Tenant, int(job.tenant_id), with_for_update=True)
        meta = _meta_row(db, int(job.tenant_id), lock=True, create=True)
        payload = dict(meta.config_json or {})
        job.final_export_sha256 = digest
        job.state = "RETENTION"
        _set_step(db, job.id, "FINAL_EXPORT", "SUCCEEDED", result={"sha256": digest})
        # After final export there is no reason to allow tenant interactive login.
        tenant.status = "SUSPENDED"
        payload["status"] = "disabled"
        meta.config_json = payload
        tenant.version = int(tenant.version or 0) + 1
        meta.version = int(meta.version or 0) + 1
        revoked = _revoke_refresh_by_tenant(db, int(job.tenant_id))
        _set_step(db, job.id, "RETENTION", "SUCCEEDED", result={
            "retentionUntil": job.retention_until.isoformat() if job.retention_until else None,
            "refreshTokensRevoked": revoked,
        })
        db.commit()
        tenant_id = int(job.tenant_id)
    finally:
        db.close()
    invalidate_tenant_subject_caches(tenant_id)
    return get_job(int(job_id))


def cancel_offboarding(user: dict, job_id: int, *, reason: str) -> dict:
    from app.models import Tenant
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因至少5个字符")
    db = _session()
    try:
        job = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.id == int(job_id), TenantOffboardingJob.is_deleted.is_(False)
        ).with_for_update()).first()
        if job is None:
            raise not_found("退租任务不存在")
        if job.state not in CANCELLABLE_STATES:
            raise AppException("DATA_CONFLICT", "已进入不可逆销毁阶段，不能取消", http_status=409)
        before = dict((job.preview_json or {}).get("beforeState") or {})
        tenant = db.get(Tenant, int(job.tenant_id), with_for_update=True)
        meta = _meta_row(db, int(job.tenant_id), lock=True, create=True)
        payload = dict(meta.config_json or {})
        tenant.status = str(before.get("rowStatus") or "ACTIVE")
        previous_meta = before.get("metaStatus")
        if previous_meta:
            payload["status"] = previous_meta
        else:
            payload.pop("status", None)
        meta.config_json = payload
        tenant.version = int(tenant.version or 0) + 1
        meta.version = int(meta.version or 0) + 1
        job.state = "CANCELLED"
        job.result_json = {**dict(job.result_json or {}), "cancelReason": str(reason).strip(), "cancelledBy": _actor_id(user)}
        job.finished_at = datetime.utcnow()
        _set_step(db, job.id, "CANCEL", "SUCCEEDED", result={"reason": str(reason).strip()})
        db.commit()
        tenant_id = int(job.tenant_id)
    finally:
        db.close()
    invalidate_tenant_subject_caches(tenant_id)
    return get_job(int(job_id))


def approve_and_purge(user: dict, job_id: int, *, expected_version: int, source_commit: str | None = None) -> dict:
    from app.models import Tenant
    from app.services.tenant_purge_registry import assert_registry_complete
    from app.services.tenant_purge_service import execute_tenant_purge

    db = _session()
    tenant_snapshot: dict | None = None
    try:
        job = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.id == int(job_id), TenantOffboardingJob.is_deleted.is_(False)
        ).with_for_update()).first()
        if job is None:
            raise not_found("退租任务不存在")
        if job.state not in {"RETENTION", "PURGE_READY", "FAILED"}:
            raise AppException("DATA_CONFLICT", f"当前状态 {job.state} 不能进入销毁", http_status=409)
        if not job.final_export_sha256:
            raise AppException("TENANT_PURGE_EXPORT_REQUIRED", "最终导出未确认，禁止销毁", http_status=409)
        if job.retention_until and job.retention_until > datetime.utcnow():
            raise AppException("TENANT_PURGE_RETENTION_ACTIVE", "仍在数据保留期，禁止销毁", http_status=409,
                               details={"retentionUntil": job.retention_until.isoformat()})
        counts = _basic_counts(db, int(job.tenant_id))
        if counts["legalHoldFileCount"]:
            job.legal_hold_blocked = True
            job.state = "BLOCKED"
            _set_step(db, job.id, "PURGE_PRECHECK", "BLOCKED", result=counts, error="LEGAL_HOLD")
            db.commit()
            raise AppException("TENANT_PURGE_LEGAL_HOLD", "存在 Legal Hold，禁止销毁", http_status=409)
        assert_registry_complete()
        tenant = db.get(Tenant, int(job.tenant_id), with_for_update=True)
        if tenant is None:
            raise not_found("租户不存在")
        meta = _meta_row(db, int(job.tenant_id), lock=True, create=True)
        current_version = _version(tenant, meta)
        if int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "租户状态已变化，请刷新后重试", http_status=409,
                               details={"expectedVersion": expected_version, "currentVersion": current_version})
        tenant_snapshot = {"tenantId": int(tenant.id), "tenantCode": tenant.tenant_code, "tenantName": tenant.school_name}
        job.approved_by = _actor_id(user)
        job.approved_at = datetime.utcnow()
        job.state = "PURGING"
        _set_step(db, job.id, "PURGE", "RUNNING")
        db.commit()
        tenant_id = int(job.tenant_id)
    finally:
        db.close()

    try:
        purge = execute_tenant_purge(tenant_id, source_commit=source_commit)
    except Exception as exc:
        db = _session()
        try:
            job = db.get(TenantOffboardingJob, int(job_id), with_for_update=True)
            if job is not None:
                job.state = "FAILED"
                job.last_error = str(exc)[:4000]
                _set_step(db, job.id, "PURGE", "FAILED", error=str(exc)[:4000])
                db.commit()
        finally:
            db.close()
        raise

    evidence = dict(purge["evidence"])
    db = _session()
    try:
        job = db.get(TenantOffboardingJob, int(job_id), with_for_update=True)
        tenant = db.get(Tenant, tenant_id, with_for_update=True)
        now = datetime.utcnow()
        if tenant is None or job is None:
            raise AppException("TENANT_PURGE_FINALIZE_FAILED", "销毁完成但控制面记录缺失，需人工处置", http_status=500)
        original_code = str(tenant_snapshot["tenantCode"])
        original_name = str(tenant_snapshot["tenantName"])
        code_hash = hashlib.sha256(original_code.encode("utf-8")).hexdigest()
        tombstone = db.scalars(select(TenantTombstone).where(TenantTombstone.tenant_id == tenant_id).with_for_update()).first()
        if tombstone is None:
            tombstone = TenantTombstone(
                tenant_id=tenant_id,
                tenant_code_hash=code_hash,
                tenant_name_snapshot=original_name,
                offboarding_job_id=int(job.id),
                reason=job.reason,
                final_export_sha256=str(job.final_export_sha256),
                purge_evidence_sha256=str(evidence["evidenceSha256"]),
                purged_at=now,
                evidence_json=evidence,
            )
            db.add(tombstone)
        tenant.status = "ARCHIVED"
        tenant.tenant_code = f"purged-{tenant_id}-{code_hash[:8]}"
        tenant.school_name = "已销毁租户"
        tenant.short_name = None
        tenant.region_code = None
        tenant.contact_name = None
        tenant.contact_phone_encrypted = None
        tenant.version = int(tenant.version or 0) + 1
        job.state = "PURGED"
        job.purge_evidence_sha256 = str(evidence["evidenceSha256"])
        job.result_json = {"purgeEvidence": evidence}
        job.last_error = None
        job.finished_at = now
        _set_step(db, job.id, "PURGE", "SUCCEEDED", result=evidence)
        db.commit()
    finally:
        db.close()
    return get_job(int(job_id))


def get_job(job_id: int) -> dict:
    db = _session()
    try:
        job = db.get(TenantOffboardingJob, int(job_id))
        if job is None or job.is_deleted:
            raise not_found("退租任务不存在")
        steps = db.scalars(select(TenantOffboardingStep).where(
            TenantOffboardingStep.job_id == int(job.id), TenantOffboardingStep.is_deleted.is_(False)
        ).order_by(TenantOffboardingStep.id)).all()
        return {
            "jobId": str(job.id), "tenantId": str(job.tenant_id), "state": job.state,
            "reason": job.reason, "version": int(job.version or 0),
            "finalExportSha256": job.final_export_sha256,
            "retentionUntil": job.retention_until.isoformat() if job.retention_until else None,
            "legalHoldBlocked": bool(job.legal_hold_blocked),
            "purgeEvidenceSha256": job.purge_evidence_sha256,
            "preview": job.preview_json or {}, "result": job.result_json or {},
            "lastError": job.last_error,
            "cancellable": job.state in CANCELLABLE_STATES,
            "irreversible": job.state in {"PURGE_READY", "PURGING", "PURGED"},
            "steps": [
                {"stepCode": s.step_code, "status": s.status, "attempts": int(s.attempts or 0),
                 "result": s.result_json or {}, "lastError": s.last_error}
                for s in steps
            ],
        }
    finally:
        db.close()


def get_active_job_for_tenant(tenant_id: int) -> dict | None:
    db = _session()
    try:
        row = db.scalars(select(TenantOffboardingJob).where(
            TenantOffboardingJob.tenant_id == int(tenant_id),
            TenantOffboardingJob.is_deleted.is_(False),
        ).order_by(TenantOffboardingJob.id.desc())).first()
        return get_job(int(row.id)) if row else None
    finally:
        db.close()
