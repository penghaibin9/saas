"""Durable, authenticated check-in continuation with atomic per-student receipts.

Requests process a bounded chunk. Closing the browser pauses continuation; a new
request resumes PENDING items, never replays completed physical check-ins.
"""
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.core.timeutil import utc_now_naive
from app.models import DormStay, StudentProfile
from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem
from app.services import affairs_dorm_service as dorm
from app.services.affairs_dorm_stay_service import _actor_id
from app.services.db_service import _tid, session
from app.services.dorm_checkin_command import checkin_in_transaction

JOB_TYPE = "DORM_CHECKIN"


def _summary(job):
    return {"jobId": str(job.id), "batchNo": job.batch_no, "status": job.status,
            "total": job.total_count, "success": job.success_count,
            "failed": job.failure_count, "pending": job.pending_count}


def _require_job(db, job_id, user, *, lock=False):
    query = select(AffairsBatchJob).where(
        AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.id == int(job_id),
        AffairsBatchJob.job_type == JOB_TYPE, AffairsBatchJob.is_deleted.is_(False),
    )
    job = db.scalars(query.with_for_update() if lock else query).first()
    if not job:
        raise not_found("入住批次不存在")
    if job.requested_by != str(_actor_id(db, user)):
        raise AppException("NO_PERMISSION", "仅可查看和继续本人发起的入住批次")
    dorm._require_dorm_scope(db, job.request_json.get("buildingIds", []), user)
    return job


def create(body, user):
    selections = sorted(
        [{"stayId": str(int(row.stayId)), "version": row.version} for row in body.items],
        key=lambda row: int(row["stayId"]),
    )
    if len({row["stayId"] for row in selections}) != len(selections):
        raise AppException("VALIDATION_ERROR", "请勿重复选择同一住宿记录")
    with session() as db:
        actor = str(_actor_id(db, user))
        existing_query = select(AffairsBatchJob).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == JOB_TYPE,
            AffairsBatchJob.idempotency_key == body.clientRequestId,
        )

        def existing_result(job):
            job = _require_job(db, job.id, user)
            if job.request_json.get("items") != selections:
                raise AppException("IDEMPOTENCY_CONFLICT", "请求编号已用于另一份入住名单")
            return _summary(job)

        existing = db.scalars(existing_query).first()
        if existing:
            return existing_result(existing)
        rows = db.execute(select(DormStay, StudentProfile).join(
            StudentProfile, StudentProfile.id == DormStay.student_id,
        ).where(
            DormStay.tenant_id == _tid(), DormStay.is_deleted.is_(False),
            DormStay.id.in_([int(row["stayId"]) for row in selections]),
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        )).all()
        by_id = {str(stay.id): (stay, student) for stay, student in rows}
        if len(by_id) != len(selections):
            raise not_found("所选住宿记录已失效，请刷新名单")
        buildings = sorted({int(stay.building_id) for stay, _ in rows})
        for building_id in buildings:
            dorm._require_dorm_scope(db, building_id, user)
        for selection in selections:
            stay, _ = by_id[selection["stayId"]]
            if stay.status != "RESERVED" or int(stay.version or 0) != selection["version"]:
                raise AppException("DATA_CONFLICT", "所选预留记录已变化，请刷新名单")
        job = AffairsBatchJob(
            tenant_id=_tid(), batch_no=f"IN-{uuid4().hex}", job_type=JOB_TYPE,
            idempotency_key=body.clientRequestId, requested_by=actor, status="PENDING",
            request_json={"items": selections, "buildingIds": buildings,
                          "arrivalConfirmed": True},
            total_count=len(selections), pending_count=len(selections),
            success_count=0, failure_count=0,
        )
        try:
            db.add(job)
            db.flush()
            for selection in selections:
                stay, student = by_id[selection["stayId"]]
                db.add(AffairsBatchJobItem(
                    tenant_id=_tid(), batch_job_id=job.id, item_key=str(stay.id),
                    biz_type="DORM_STAY", biz_id=stay.id, action="CHECKIN",
                    expected_version=selection["version"], status="PENDING",
                    payload_json={"studentId": str(stay.student_id), "bedId": str(stay.bed_id),
                                  "studentName": student.real_name, "studentNo": student.student_no},
                ))
            dorm._audit(db, "DORM_CHECKIN_BATCH", job.id, "CREATE", f"count={len(selections)}")
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalars(existing_query).first()
            if existing:
                return existing_result(existing)
            raise
        return _summary(job)


def detail(job_id, user, *, page=1, page_size=50):
    with session() as db:
        job = _require_job(db, job_id, user)
        items = db.scalars(select(AffairsBatchJobItem).where(
            AffairsBatchJobItem.tenant_id == _tid(), AffairsBatchJobItem.batch_job_id == job.id,
            AffairsBatchJobItem.is_deleted.is_(False),
        ).order_by(AffairsBatchJobItem.id).offset((page - 1) * page_size).limit(page_size)).all()
        return {**_summary(job), "items": [
            {"itemId": str(row.id), "stayId": str(row.biz_id), **row.payload_json,
             "status": row.status, "error": row.error_message, "result": row.result_json}
            for row in items], "page": page, "pageSize": page_size}


def recent(user):
    with session() as db:
        ids = db.scalars(select(AffairsBatchJob.id).where(
            AffairsBatchJob.tenant_id == _tid(), AffairsBatchJob.job_type == JOB_TYPE,
            AffairsBatchJob.requested_by == str(_actor_id(db, user)),
            AffairsBatchJob.is_deleted.is_(False),
        ).order_by(AffairsBatchJob.id.desc()).limit(10)).all()
        result = []
        for job_id in ids:
            try:
                result.append(_summary(_require_job(db, job_id, user)))
            except AppException as error:
                if error.code not in ("NO_PERMISSION", "NO_DATA_SCOPE"):
                    raise
        return {"items": result}


def run(job_id, user, *, limit=20):
    result = None
    for _ in range(min(max(int(limit), 1), 20)):
        with session() as db:
            # Serializes competing continuations. Receipt and business commit together.
            job = _require_job(db, job_id, user, lock=True)
            item = db.scalars(select(AffairsBatchJobItem).where(
                AffairsBatchJobItem.tenant_id == _tid(), AffairsBatchJobItem.batch_job_id == job.id,
                AffairsBatchJobItem.status == "PENDING", AffairsBatchJobItem.is_deleted.is_(False),
            ).order_by(AffairsBatchJobItem.id).limit(1).with_for_update()).first()
            if item is None:
                return _summary(job)
            now = utc_now_naive()
            job.started_at = job.started_at or now
            item.started_at = now
            item.attempt_count += 1
            try:
                with db.begin_nested():
                    receipt = checkin_in_transaction(
                        db, item.payload_json["bedId"], user, item.payload_json["studentId"],
                        expected_stay_id=item.biz_id, expected_stay_version=item.expected_version,
                    )
                item.status, item.result_json = "SUCCESS", receipt
                job.success_count += 1
            except AppException as error:
                # Permission loss stops continuation; never converts it into a business failure.
                if error.http_status in (401, 403):
                    raise
                item.status = "FAILED"
                item.error_code, item.error_message = error.code, error.message[:1000]
                job.failure_count += 1
            item.completed_at = utc_now_naive()
            job.pending_count -= 1
            job.status = ("RUNNING" if job.pending_count else
                          "PARTIAL_SUCCESS" if job.failure_count and job.success_count else
                          "FAILED" if job.failure_count else "SUCCESS")
            if not job.pending_count:
                job.completed_at = item.completed_at
            dorm._audit(db, "DORM_CHECKIN_BATCH", job.id, item.status, f"stay={item.biz_id}")
            db.commit()
            result = _summary(job)
    return result
