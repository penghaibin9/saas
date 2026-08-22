"""Final safety guard for tenant offboarding retry/cancellation semantics."""
from __future__ import annotations

from sqlalchemy import delete, select, text

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.core.exceptions import AppException
    from app.models.tenant_offboarding import TenantOffboardingJob
    from app.services import tenant_offboarding_service as offboarding

    # BLOCKED/FAILED are unresolved jobs, not historical terminal records.  A
    # second offboarding chain for the same tenant would make purge evidence
    # ambiguous and could race a retry, so request_offboarding must see them.
    offboarding.ACTIVE_STATES.update({"BLOCKED", "FAILED"})
    # BLOCKED is still pre-destructive (e.g. Legal Hold); an operator may cancel
    # it. FAILED may already be partially destructive and is therefore retry-only.
    offboarding.CANCELLABLE_STATES.add("BLOCKED")

    def revoke_refresh_by_tenant(db, tenant_id: int) -> int:
        """Revoke every refresh token that can still name a tenant user.

        Soft-deleted users are intentionally included.  Their account row still
        identifies tenant ownership and an old refresh token must not survive a
        tenant freeze merely because the user was deactivated before offboarding.
        """
        from app.models import AuthRefreshToken, User

        user_ids = [f"db-{int(uid)}" for uid in db.scalars(select(User.id).where(
            User.tenant_id == int(tenant_id)
        )).all()]
        deleted_count = 0
        for start in range(0, len(user_ids), 500):
            batch = user_ids[start:start + 500]
            if not batch:
                continue
            result = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id.in_(batch)))
            deleted_count += int(result.rowcount or 0)
        return deleted_count

    offboarding._revoke_refresh_by_tenant = revoke_refresh_by_tenant
    original_approve = offboarding.approve_and_purge

    def _tenant_for_job(job_id: int) -> int | None:
        db = offboarding._session()
        try:
            job = db.scalars(select(TenantOffboardingJob).where(
                TenantOffboardingJob.id == int(job_id),
                TenantOffboardingJob.is_deleted.is_(False),
            )).first()
            return int(job.tenant_id) if job is not None else None
        finally:
            db.close()

    def approve_and_purge(user: dict, job_id: int, *, expected_version: int,
                          source_commit: str | None = None) -> dict:
        tenant_id = _tenant_for_job(int(job_id))
        if tenant_id is None:
            # Preserve the canonical not-found contract from the underlying service.
            return original_approve(
                user, int(job_id), expected_version=int(expected_version), source_commit=source_commit,
            )

        # MySQL named locks are connection-scoped. Holding this dedicated session
        # across the destructive phase prevents two workers from purging the same
        # tenant concurrently. If the worker is killed, MySQL releases the lock
        # with the dead connection, so a later request can safely resume a job that
        # was stranded in PURGING after the process died.
        lock_name = f"saas:tenant-purge:{tenant_id}"
        lock_db = offboarding._session()
        acquired = False
        try:
            try:
                acquired = int(lock_db.scalar(
                    text("SELECT GET_LOCK(:lock_name, 0)"), {"lock_name": lock_name}
                ) or 0) == 1
            except Exception as exc:  # noqa: BLE001
                raise AppException(
                    "TENANT_PURGE_LOCK_UNAVAILABLE",
                    "无法取得租户销毁数据库互斥锁，拒绝继续物理销毁",
                    http_status=503,
                ) from exc
            if not acquired:
                raise AppException(
                    "TENANT_PURGE_ALREADY_RUNNING",
                    "该租户已有销毁执行器正在运行，请勿并发重试",
                    http_status=409,
                )

            db = offboarding._session()
            try:
                job = db.scalars(select(TenantOffboardingJob).where(
                    TenantOffboardingJob.id == int(job_id),
                    TenantOffboardingJob.tenant_id == int(tenant_id),
                    TenantOffboardingJob.is_deleted.is_(False),
                ).with_for_update()).first()
                if job is not None and job.state == "PURGING":
                    # Reaching this branch while holding GET_LOCK proves no live
                    # execution still owns the tenant purge. The previous process
                    # therefore died after committing PURGING; convert that stranded
                    # state to the canonical retryable FAILED state and let the
                    # idempotent purge executor resume from its residual data.
                    job.state = "FAILED"
                    job.last_error = "previous purge execution was interrupted; resuming idempotently"
                    offboarding._set_step(
                        db, int(job.id), "PURGE", "FAILED",
                        result=dict(job.result_json or {}).get("purgeEvidence"),
                        error=job.last_error,
                    )
                    db.commit()
                elif job is not None and job.state == "BLOCKED":
                    counts = offboarding._basic_counts(db, int(job.tenant_id))
                    if counts["legalHoldFileCount"]:
                        raise AppException(
                            "TENANT_PURGE_LEGAL_HOLD",
                            "Legal Hold 仍未解除，禁止续跑物理销毁",
                            http_status=409,
                            details={"legalHoldFileCount": counts["legalHoldFileCount"]},
                        )
                    # Re-enter the normal retention gate; original_approve will
                    # recheck final export, retention time, registry and version.
                    job.legal_hold_blocked = False
                    job.state = "RETENTION"
                    offboarding._set_step(
                        db, int(job.id), "PURGE_PRECHECK", "SUCCEEDED",
                        result={"legalHoldCleared": True, **counts},
                    )
                    db.commit()
            finally:
                db.close()

            return original_approve(
                user, int(job_id), expected_version=int(expected_version), source_commit=source_commit,
            )
        finally:
            if acquired:
                try:
                    lock_db.scalar(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name})
                except Exception:  # noqa: BLE001
                    # Closing the owning connection below is itself a lock release.
                    pass
            lock_db.close()

    offboarding.approve_and_purge = approve_and_purge
    _INSTALLED = True
