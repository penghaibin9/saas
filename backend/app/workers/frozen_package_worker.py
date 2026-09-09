"""External worker entrypoint for PLAT-A frozen package FileJobs."""
from __future__ import annotations

import os
import socket

from sqlalchemy import select

from app.core.context import get_tenant, set_tenant
from app.db.session import get_sessionmaker
from app.models.file import FileJob
from app.modules.platform_integrity.file_job_service import (
    FROZEN_PACKAGE_JOB_TYPE,
    claim_next_frozen_package_job,
    run_claimed_frozen_package_job,
)


def process_pending_frozen_packages(*, limit: int = 20, worker_id: str | None = None,
                                    tenant_id: int | None = None) -> dict:
    """Bound one pass and isolate tenant context before every claim/build."""
    batch_size = max(1, min(int(limit or 20), 100))
    identity = worker_id or os.getenv("FROZEN_PACKAGE_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    db = get_sessionmaker()()
    try:
        tenant_query = select(FileJob.tenant_id).where(
            FileJob.job_type == FROZEN_PACKAGE_JOB_TYPE,
            FileJob.status.in_(("PENDING", "RETRY", "RUNNING")),
            FileJob.is_deleted.is_(False),
        )
        if tenant_id is not None:
            tenant_query = tenant_query.where(FileJob.tenant_id == int(tenant_id))
        tenant_ids = list(db.scalars(
            tenant_query.distinct().order_by(FileJob.tenant_id).limit(batch_size)
        ).all())
    finally:
        db.close()
    previous = get_tenant()
    processed = succeeded = failed = 0
    try:
        while processed < batch_size and tenant_ids:
            made_progress = False
            for tenant_id in tenant_ids:
                if processed >= batch_size:
                    break
                set_tenant(int(tenant_id))
                job_id = claim_next_frozen_package_job(worker_id=identity)
                if job_id is None:
                    continue
                made_progress = True
                processed += 1
                try:
                    run_claimed_frozen_package_job(job_id=job_id, worker_id=identity)
                    succeeded += 1
                except Exception:
                    failed += 1
            if not made_progress:
                break
    finally:
        set_tenant(previous)
    return {"processed": processed, "succeeded": succeeded, "failed": failed}


__all__ = ["process_pending_frozen_packages"]
