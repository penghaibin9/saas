"""Canonical identity-import worker.

Run with::

    python -m app.workers.identity_import_worker

The file-scan worker owns ClamAV scanning.  This worker owns the next durable
transition: once the source FileObject is CLEAN/AVAILABLE it claims the pending
ImportJob, restores the original tenant/initiator context and advances the
existing normalized-staging authority.  Browser polling remains a pure read.
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import time
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from app.core.context import (
    get_current_user_ctx,
    get_tenant,
    set_current_user,
    set_tenant,
)
from app.core.tenant_scoped import tenant_get
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob
from app.models.file import FileObject
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES
from app.services.identity_import_scan_orchestrator import (
    PENDING_ADAPTER,
    refresh_identity_import_job,
)

log = logging.getLogger("identity-import-worker")

CLAIMED = "WORKER_CLAIMED"
CLAIM_STALE_SECONDS = max(60, int(os.getenv("IDENTITY_IMPORT_STALE_LOCK_SECONDS", "600")))
POLL_SECONDS = max(0.2, float(os.getenv("IDENTITY_IMPORT_POLL_SECONDS", "2")))


def _now() -> datetime:
    return datetime.utcnow()


def _claim_one(worker_id: str) -> dict | None:
    """Claim one scan-clean canonical identity job using MySQL SKIP LOCKED."""
    stale_before = _now() - timedelta(seconds=CLAIM_STALE_SECONDS)
    db = get_sessionmaker()()
    try:
        stmt = (
            select(ImportJob, FileObject)
            .join(
                FileObject,
                (FileObject.id == ImportJob.source_file_id)
                & (FileObject.tenant_id == ImportJob.tenant_id),
            )
            .where(
                ImportJob.adapter_type == PENDING_ADAPTER,
                ImportJob.is_deleted.is_(False),
                FileObject.is_deleted.is_(False),
                FileObject.scan_status.in_(tuple(READY_SCAN_STATES)),
                or_(
                    ImportJob.status == "SCANNING",
                    (
                        (ImportJob.status == CLAIMED)
                        & (ImportJob.updated_at < stale_before)
                    ),
                ),
            )
            .order_by(ImportJob.created_at, ImportJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        pair = db.execute(stmt).first()
        if pair is None:
            db.rollback()
            return None
        job, file_obj = pair
        if not is_downloadable_status(file_obj.status):
            db.rollback()
            return None
        result = dict(job.result_json or {})
        job.status = CLAIMED
        job.result_json = {
            **result,
            "workerRequired": True,
            "workerId": str(worker_id),
            "workerClaimedAt": _now().isoformat() + "Z",
        }
        job.version = int(job.version or 0) + 1
        db.commit()
        return {
            "jobId": str(job.id),
            "tenantId": int(job.tenant_id),
            "operatorId": int(job.operator_id or job.created_by or 0),
            "operatorName": str(job.operator_name or "身份导入任务创建人"),
            "kind": str(job.import_type or "").replace("IDENTITY_", ""),
        }
    finally:
        db.close()


def _worker_actor(claim: dict) -> dict:
    """Narrow service reconstruction of the already-authorized initiating actor.

    Upload creation has already passed ``systemAdmin.user.import`` and, for
    students, ``student.import`` + tenant feature checks.  The worker does not
    confirm/create accounts; it only performs malware-cleared parse/validation.
    Final confirmation still traverses the canonical authorization path.
    """
    operator_id = int(claim.get("operatorId") or 0)
    return {
        "userId": f"db-{operator_id}" if operator_id else "identity-import-worker",
        "realName": claim.get("operatorName") or "身份导入任务创建人",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(claim["tenantId"]),
        "permissions": ["systemAdmin.user.import", "student.import"],
        "serviceActor": "IDENTITY_IMPORT_WORKER",
    }


def process_next_identity_import(worker_id: str | None = None) -> dict:
    identity = worker_id or os.getenv("IDENTITY_IMPORT_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    claim = _claim_one(identity)
    if claim is None:
        return {"processed": False, "reason": "empty"}

    previous_tenant = get_tenant()
    previous_user = get_current_user_ctx()
    actor = _worker_actor(claim)
    try:
        set_tenant({"tenantId": str(claim["tenantId"])})
        set_current_user(actor)
        result = refresh_identity_import_job(
            claim["jobId"],
            user=actor,
            worker_claimed=True,
        )
        return {
            "processed": True,
            "jobId": claim["jobId"],
            "tenantId": str(claim["tenantId"]),
            "status": result.get("status"),
            "totalRows": int(result.get("totalRows") or 0),
            "validRows": int(result.get("validRows") or 0),
            "invalidRows": int(result.get("invalidRows") or 0),
        }
    except Exception as exc:  # noqa: BLE001 - persist recoverable worker state
        db = get_sessionmaker()()
        try:
            job = tenant_get(db, ImportJob, int(claim["jobId"]))
            if job is not None and job.status == CLAIMED:
                payload = dict(job.result_json or {})
                job.status = "SCANNING"
                job.error_message = str(exc)[:4000]
                job.result_json = {
                    **payload,
                    "workerLastError": str(exc)[:2000],
                    "workerFailedAt": _now().isoformat() + "Z",
                }
                job.version = int(job.version or 0) + 1
                db.commit()
        finally:
            db.close()
        raise
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)


def run(*, once: bool = False, worker_id: str | None = None) -> int:
    processed = 0
    while True:
        result = process_next_identity_import(worker_id)
        if result.get("processed"):
            processed += 1
            log.info("identity import worker result: %s", result)
        elif once:
            return processed
        else:
            time.sleep(POLL_SECONDS)
        if once:
            return processed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="处理至多一个身份导入任务后退出")
    parser.add_argument("--worker-id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(once=args.once, worker_id=args.worker_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
