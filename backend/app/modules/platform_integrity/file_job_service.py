"""Frozen evidence package jobs built on the existing FileJob authority."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.models.file import ArchiveManifest, FileJob
from app.modules.platform_integrity.deterministic_package import STANDARD_PROFILE_V1
from app.modules.platform_integrity.frozen_package_service import (
    PACKAGEABLE_MANIFEST_STATUSES,
    build_frozen_package_for_job,
)
from app.services.db_service import _tid, session

FROZEN_PACKAGE_JOB_TYPE = "FROZEN_EVIDENCE_PACKAGE"
_PERMANENT_PACKAGE_JOB_ERRORS = frozenset({
    "FILE_JOB_SOURCE_CHANGED",
    "FROZEN_MANIFEST_STATE_INVALID",
    "FROZEN_SNAPSHOT_CARDINALITY_INVALID",
    "FROZEN_MANIFEST_ITEM_DRIFT",
    "LEGACY_MANIFEST_UNSUPPORTED",
    "PACKAGE_ENTRY_PATH_CONFLICT",
    "PACKAGE_PROFILE_UNSUPPORTED",
})


def package_job_dedupe_key(*, tenant_id: int, manifest_id: int, revision: int, manifest_sha256: str, profile_code: str) -> str:
    identity = f"{tenant_id}:{manifest_id}:{revision}:{manifest_sha256.lower()}:{profile_code.upper()}"
    return f"FROZEN_PACKAGE:{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def enqueue_frozen_package(db, *, manifest_id: int, profile_code: str = STANDARD_PROFILE_V1) -> FileJob:
    tenant_id = _tid()
    profile = str(profile_code or "").strip().upper()
    if profile != STANDARD_PROFILE_V1:
        raise AppException("PACKAGE_PROFILE_UNSUPPORTED", "仅支持 STANDARD_V1 冻结包规范", http_status=422)
    manifest = db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == tenant_id,
        ArchiveManifest.id == int(manifest_id),
        ArchiveManifest.is_deleted.is_(False),
    )).first()
    if not manifest:
        raise not_found("冻结清单不存在")
    if str(manifest.status or "").upper() not in PACKAGEABLE_MANIFEST_STATUSES:
        raise AppException("FROZEN_MANIFEST_STATE_INVALID", "当前清单状态不允许生成冻结证据包", http_status=409)
    if not manifest.manifest_sha256:
        raise AppException("FROZEN_MANIFEST_DIGEST_MISSING", "冻结清单缺少摘要", http_status=409)
    key = package_job_dedupe_key(
        tenant_id=tenant_id,
        manifest_id=int(manifest.id),
        revision=int(manifest.revision or 1),
        manifest_sha256=str(manifest.manifest_sha256),
        profile_code=profile,
    )
    existing = db.scalars(select(FileJob).where(
        FileJob.tenant_id == tenant_id,
        FileJob.dedupe_key == key,
        FileJob.is_deleted.is_(False),
    )).first()
    if existing:
        return existing
    job = FileJob(
        tenant_id=tenant_id,
        job_type=FROZEN_PACKAGE_JOB_TYPE,
        dedupe_key=key,
        status="PENDING",
        attempts=0,
        max_attempts=5,
        available_at=datetime.utcnow(),
        payload_json={
            "tenantId": str(tenant_id),
            "manifestId": str(manifest.id),
            "revision": int(manifest.revision or 1),
            "manifestSha256": str(manifest.manifest_sha256),
            "profileCode": profile,
        },
    )
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
        return job
    except IntegrityError:
        winner = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.dedupe_key == key,
            FileJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if winner:
            return winner
        raise


def request_frozen_package_build(*, manifest_id: int, profile_code: str = STANDARD_PROFILE_V1) -> dict:
    """Idempotently request worker execution; a manual retry may revive a dead job."""
    tenant_id = _tid()
    with session() as db:
        job = enqueue_frozen_package(db, manifest_id=manifest_id, profile_code=profile_code)
        if str(job.status or "").upper() == "DEAD":
            job.status = "RETRY"
            job.attempts = 0
            job.available_at = datetime.utcnow()
            job.locked_at = None
            job.locked_by = None
            job.last_error = None
            job.version = int(job.version or 0) + 1
        db.commit()
        return {
            "jobId": str(job.id),
            "tenantId": str(tenant_id),
            "status": str(job.status or "PENDING").upper(),
        }


def claim_next_frozen_package_job(*, worker_id: str, stale_after_seconds: int = 600) -> int | None:
    tenant_id = _tid()
    now = datetime.utcnow()
    stale_before = now - timedelta(seconds=max(60, int(stale_after_seconds)))
    with session() as db:
        job = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
            FileJob.is_deleted.is_(False),
            FileJob.available_at <= now,
            or_(
                FileJob.status.in_(("PENDING", "RETRY")),
                (FileJob.status == "RUNNING") & (FileJob.locked_at < stale_before),
            ),
        ).order_by(FileJob.available_at, FileJob.id).limit(1).with_for_update(skip_locked=True)).first()
        if not job:
            db.rollback()
            return None
        job.status = "RUNNING"
        job.attempts = int(job.attempts or 0) + 1
        job.locked_at = now
        job.locked_by = str(worker_id)[:120]
        job.last_error = None
        db.commit()
        return int(job.id)


def run_claimed_frozen_package_job(*, job_id: int, worker_id: str) -> dict:
    tenant_id = _tid()
    with session() as db:
        job = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.id == int(job_id),
            FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
            FileJob.is_deleted.is_(False),
        )).first()
        if not job:
            raise not_found("冻结包任务不存在")
        if job.status == "SUCCEEDED":
            return dict(job.result_json or {})
        if job.status != "RUNNING" or str(job.locked_by or "") != str(worker_id):
            raise AppException("FILE_JOB_LEASE_LOST", "冻结包任务租约已失效", http_status=409)
        payload = dict(job.payload_json or {})
        if int(payload.get("tenantId") or 0) != tenant_id:
            raise AppException("TENANT_SCOPE_MISMATCH", "任务租户与执行上下文不一致", http_status=409)

    try:
        result = build_frozen_package_for_job(
            manifest_id=int(payload["manifestId"]),
            profile_code=str(payload["profileCode"]),
            expected_revision=int(payload["revision"]),
            expected_manifest_sha256=str(payload["manifestSha256"]),
        ).as_dict()
    except Exception as exc:
        with session() as db:
            job = db.scalars(select(FileJob).where(
                FileJob.tenant_id == tenant_id,
                FileJob.id == int(job_id),
                FileJob.is_deleted.is_(False),
            ).with_for_update()).first()
            if job and job.status == "RUNNING" and str(job.locked_by or "") == str(worker_id):
                error_text = f"{exc.code}: {exc.message}" if isinstance(exc, AppException) else str(exc)
                job.last_error = error_text[:4000]
                job.locked_at = None
                job.locked_by = None
                permanent = isinstance(exc, AppException) and exc.code in _PERMANENT_PACKAGE_JOB_ERRORS
                if permanent or int(job.attempts or 0) >= int(job.max_attempts or 5):
                    job.status = "DEAD"
                else:
                    job.status = "RETRY"
                    job.available_at = datetime.utcnow() + timedelta(seconds=min(300, 2 ** int(job.attempts or 1)))
                db.commit()
        raise

    with session() as db:
        job = db.scalars(select(FileJob).where(
            FileJob.tenant_id == tenant_id,
            FileJob.id == int(job_id),
            FileJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if not job or job.status != "RUNNING" or str(job.locked_by or "") != str(worker_id):
            raise AppException("FILE_JOB_LEASE_LOST", "冻结包任务租约已失效", http_status=409)
        job.status = "SUCCEEDED"
        job.result_json = result
        job.locked_at = None
        job.locked_by = None
        job.last_error = None
        db.commit()
    return result


__all__ = [
    "FROZEN_PACKAGE_JOB_TYPE",
    "claim_next_frozen_package_job",
    "enqueue_frozen_package",
    "package_job_dedupe_key",
    "request_frozen_package_build",
    "run_claimed_frozen_package_job",
]
