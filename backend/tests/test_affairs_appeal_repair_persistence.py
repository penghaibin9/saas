"""异议/申诉补偿专用任务、租约回收与迟到 worker 防覆盖。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

TID = 1000000000000000001


def _set_context():
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "db-1", "realName": "学校管理员", "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN", "tenantId": str(TID),
    })


def _clear_context():
    from app.core.context import set_current_user, set_tenant
    set_current_user(None)
    set_tenant(None)


def test_appeal_repair_uses_dedicated_job_and_persists_lease(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsRepairJob
    from app.services import affairs_appeal_repair_service as repair

    _set_context()
    try:
        repair.enqueue("AID_OBJECTION_REVIEW", 880001, "TODO_SYNC", RuntimeError("down"))
        db = get_sessionmaker()()
        row = db.scalars(select(AffairsRepairJob).where(
            AffairsRepairJob.tenant_id == TID,
            AffairsRepairJob.dedup_key == repair._key("AID_OBJECTION_REVIEW", 880001, "TODO_SYNC"),
        )).one()
        assert row.state == "PENDING"
        assert row.attempts == 0
        assert row.source_row_id == 880001
        db.close()

        claimed = repair._claim(10, worker_id="worker-a", lease_seconds=60)
        item = next(x for x in claimed if x["rowId"] == 880001)
        assert item["attempts"] == 1
        assert item["leaseOwner"] == "worker-a"

        db = get_sessionmaker()()
        claimed_row = db.get(AffairsRepairJob, item["id"])
        assert claimed_row.state == "PROCESSING"
        assert claimed_row.lease_owner == "worker-a"
        assert claimed_row.lease_until is not None
        db.close()
    finally:
        _clear_context()


def test_expired_processing_is_reclaimed_and_old_worker_cannot_finish(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsRepairJob
    from app.services import affairs_appeal_repair_service as repair

    _set_context()
    try:
        now = datetime.utcnow()
        db = get_sessionmaker()()
        job = AffairsRepairJob(
            tenant_id=TID, dedup_key=repair._key("FUNDING_APPEAL_REVIEW", 880002, "RESULT_NOTICE"),
            todo_type="FUNDING_APPEAL_REVIEW", source_row_id=880002, stage="RESULT_NOTICE",
            state="PROCESSING", attempts=1, next_run_at=now - timedelta(minutes=10),
            lease_owner="dead-worker", lease_until=now - timedelta(seconds=1),
        )
        db.add(job); db.commit(); job_id = int(job.id); db.close()

        claimed = repair._claim(10, worker_id="worker-b", lease_seconds=60)
        item = next(x for x in claimed if x["id"] == job_id)
        assert item["attempts"] == 2
        assert item["leaseOwner"] == "worker-b"

        repair._finish(job_id, True, lease_owner="dead-worker")
        db = get_sessionmaker()(); row = db.get(AffairsRepairJob, job_id)
        assert row.state == "PROCESSING"
        assert row.lease_owner == "worker-b"
        db.close()

        repair._finish(job_id, True, lease_owner="worker-b")
        db = get_sessionmaker()(); row = db.get(AffairsRepairJob, job_id)
        assert row.state == "COMPLETED"
        assert row.lease_owner is None
        db.close()
    finally:
        _clear_context()

def test_dead_job_can_be_listed_and_manually_requeued_with_version_lock(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AffairsRepairJob
    from app.services import affairs_appeal_repair_service as repair

    _set_context()
    try:
        now = datetime.utcnow()
        db = get_sessionmaker()()
        job = AffairsRepairJob(
            tenant_id=TID, dedup_key=repair._key("DISCIPLINE_APPEAL_REVIEW", 880003, "RESULT_NOTICE"),
            todo_type="DISCIPLINE_APPEAL_REVIEW", source_row_id=880003, stage="RESULT_NOTICE",
            state="DEAD", attempts=8, next_run_at=now, last_error="RuntimeError", version=3,
        )
        db.add(job); db.commit(); job_id = int(job.id); db.close()

        page = repair.list_jobs(state="DEAD", page=1, page_size=20)
        listed = next(item for item in page["items"] if int(item["jobId"]) == job_id)
        assert listed["attempts"] == 8
        assert listed["version"] == 3

        try:
            repair.requeue_dead(job_id, expected_version=2)
            assert False, "stale version must fail"
        except AppException as exc:
            assert exc.code == "DATA_CONFLICT"

        result = repair.requeue_dead(job_id, expected_version=3)
        assert result["state"] == "PENDING"
        assert result["attempts"] == 0
        assert result["version"] == 4

        db = get_sessionmaker()(); row = db.get(AffairsRepairJob, job_id)
        assert row.state == "PENDING"
        assert row.attempts == 0
        assert row.lease_owner is None and row.lease_until is None
        db.close()
    finally:
        _clear_context()
