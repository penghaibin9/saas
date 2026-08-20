"""Final safety guard for tenant offboarding retry/cancellation semantics."""
from __future__ import annotations

from sqlalchemy import select

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

    original_approve = offboarding.approve_and_purge

    def approve_and_purge(user: dict, job_id: int, *, expected_version: int,
                          source_commit: str | None = None) -> dict:
        db = offboarding._session()
        try:
            job = db.scalars(select(TenantOffboardingJob).where(
                TenantOffboardingJob.id == int(job_id),
                TenantOffboardingJob.is_deleted.is_(False),
            ).with_for_update()).first()
            if job is not None and job.state == "BLOCKED":
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

    offboarding.approve_and_purge = approve_and_purge
    _INSTALLED = True
