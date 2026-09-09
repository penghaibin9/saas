"""Durable allocation publication; queue reads never execute housing commands.

The worker holds the job row lock through publication and its receipt transaction.
A crashed worker releases that lock: RUNNING work is recoverable without a lease
expiry guessing when a large school should have finished.
"""
from uuid import uuid4

from sqlalchemy import func, select

from app.core.context import (get_current_user_ctx, get_tenant, set_current_user,
                              set_tenant)
from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.core.timeutil import utc_now_naive
from app.db.session import get_sessionmaker
from app.models import DormAllocationItem
from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem
from app.services import dorm_allocation_service as allocation
from app.services import affairs_dorm_service as dorm
from app.services.affairs_dorm_stay_service import _actor_id
from app.services.db_service import _tid, session

JOB_TYPE = "DORM_ALLOCATION_PUBLISH"
PERMISSION = "studentAffairs.dorm.allocation.manage"


def _row(job):
    return {"jobId": str(job.id), "batchId": str(job.request_json["batchId"]),
            "status": job.status, "total": job.total_count,
            "success": job.success_count, "error": job.last_error or "",
            "version": job.request_json["version"]}


def _authorize_batch(db, batch_id, user):
    enforce_permission(user, PERMISSION)
    batch = allocation._batch(db, batch_id)
    allocation._resource_rows(db, batch.resource_scope_json or {}, user)
    return batch


def enqueue(batch_id, version, user):
    with session() as db:
        # Serialize submissions for the same plan, including different operators.
        batch = allocation._batch(db, batch_id, for_update=True)
        _authorize_batch(db, batch.id, user)
        key = f"publish:{batch.id}:{version}"
        existing = db.scalar(select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == JOB_TYPE,
            AffairsBatchJob.idempotency_key == key,
        ))
        if existing:
            return _row(existing)
        if batch.status != "DRAFT" or int(batch.version or 0) != version:
            raise AppException("DATA_CONFLICT", "分配方案已变化，请刷新核对后发布")
        count = db.scalar(select(func.count()).select_from(DormAllocationItem).where(
            DormAllocationItem.tenant_id == _tid(),
            DormAllocationItem.allocation_batch_id == batch.id,
            DormAllocationItem.status == "PROPOSED", DormAllocationItem.is_deleted.is_(False),
        )) or 0
        if batch.mode != "STUDENT_SELECT" and count == 0:
            raise AppException("INVALID_STATE", "请先生成并核对分配方案")
        actor_id = _actor_id(db, user)
        actor = {"userId": f"db-{actor_id}", "tenantId": str(_tid()),
                 "activeContextId": (user or {}).get("activeContextId"),
                 "currentRoleCode": (user or {}).get("currentRoleCode")}
        job = AffairsBatchJob(
            tenant_id=_tid(), batch_no=f"PUB-{uuid4().hex}", job_type=JOB_TYPE,
            idempotency_key=key, requested_by=str(actor_id), status="PENDING",
            total_count=count, success_count=0, failure_count=0, pending_count=count,
            request_json={"batchId": str(batch.id), "version": version, "actor": actor},
        )
        db.add(job); db.flush()
        db.add(AffairsBatchJobItem(
            tenant_id=_tid(), batch_job_id=job.id, item_key=str(batch.id),
            biz_type="DORM_ALLOCATION_BATCH", biz_id=batch.id, action="PUBLISH",
            expected_version=version, status="PENDING", attempt_count=0,
        ))
        dorm._audit(db, "DORM_ALLOCATION_BATCH", batch.id, "QUEUE_PUBLISH", f"job={job.id}")
        db.commit()
        return _row(job)


def latest(batch_id, user):
    with session() as db:
        batch = _authorize_batch(db, batch_id, user)
        job = db.scalar(select(AffairsBatchJob).join(
            AffairsBatchJobItem, AffairsBatchJobItem.batch_job_id == AffairsBatchJob.id,
        ).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == JOB_TYPE,
            AffairsBatchJob.is_deleted.is_(False),
            AffairsBatchJobItem.tenant_id == _tid(), AffairsBatchJobItem.biz_id == batch.id,
            AffairsBatchJobItem.is_deleted.is_(False),
        ).order_by(AffairsBatchJob.id.desc()).limit(1))
        return _row(job) if job else None


def _live_actor(db, snapshot):
    # Restore the initiating identity from current authority, never cached permissions
    # or a fabricated SCHOOL_ADMIN identity. Revoked roles/accounts/tenants fail closed.
    from app.services import auth_service_db as auth
    from app.services.module_access_service import assert_module_access
    account = auth._load_token_user(db, snapshot)
    auth._ensure_tenant_login_allowed(db, account)
    contexts = auth._role_contexts(db, account)
    current = auth._pick_context(contexts, context_id=snapshot.get("activeContextId"),
                                 role_code=snapshot.get("currentRoleCode"))
    if not current or current["roleCode"] != snapshot.get("currentRoleCode"):
        raise AppException("NO_PERMISSION", "发布人的原岗位已失效，请重新核对授权")
    actor = auth._claims(db, account, current, contexts, "PC")
    assert_module_access(int(account.tenant_id), "studentAffairs", write=True)
    enforce_permission(actor, PERMISSION)
    return actor


def run_one():
    """Process at most one job. SKIP LOCKED permits other workers to advance others."""
    with get_sessionmaker()() as db:
        job = db.scalar(select(AffairsBatchJob).where(
            AffairsBatchJob.job_type == JOB_TYPE,
            AffairsBatchJob.status.in_(["PENDING", "RUNNING"]),
            AffairsBatchJob.is_deleted.is_(False),
        ).order_by(AffairsBatchJob.id).limit(1).with_for_update(skip_locked=True))
        if not job:
            return {"processed": False}
        job.status = "RUNNING"
        job.started_at = job.started_at or utc_now_naive()
        job_id, tenant_id = job.id, job.tenant_id
        db.commit()  # Make queued/running state visible before the long transaction.
    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    try:
        set_tenant({"tenantId": str(tenant_id)})
        with session() as db:
            job = db.scalar(select(AffairsBatchJob).where(
                AffairsBatchJob.id == job_id, AffairsBatchJob.tenant_id == _tid(),
                AffairsBatchJob.job_type == JOB_TYPE, AffairsBatchJob.status == "RUNNING",
                AffairsBatchJob.is_deleted.is_(False),
            ).with_for_update(skip_locked=True))
            if not job:
                return {"processed": False}
            item = db.scalar(select(AffairsBatchJobItem).where(
                AffairsBatchJobItem.batch_job_id == job.id,
                AffairsBatchJobItem.tenant_id == _tid(),
                AffairsBatchJobItem.is_deleted.is_(False),
            ))
            if not item:
                raise not_found("发布任务回执不存在")
            item.attempt_count += 1
            item.started_at = utc_now_naive()
            try:
                with db.begin_nested():
                    actor = _live_actor(db, job.request_json["actor"])
                    set_current_user(actor)
                    result = allocation.publish_in_transaction(
                        db, item.biz_id, actor, expected_version=item.expected_version,
                    )
                    db.flush()
                job.status, job.success_count = "SUCCESS", job.total_count
                job.failure_count, job.last_error = 0, None
                item.status, item.result_json = "SUCCESS", result
            except AppException as error:
                job.status, job.failure_count = "FAILED", job.total_count
                job.last_error = error.message
                item.status, item.error_code, item.error_message = "FAILED", str(error.code), error.message
            job.pending_count = 0
            job.completed_at = item.completed_at = utc_now_naive()
            db.commit()  # Housing publication and success receipt commit together.
            return {"processed": True, **_row(job)}
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)
