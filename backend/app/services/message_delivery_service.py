"""消息投递：分批写个人收件 + 万人级作业租约领取。

HTTP 发布只受理；大名单入 t_message_delivery_job，由调度器领取。
幂等：campaign + receiver_user_id + GLOBAL 唯一约束 / 写入前查询。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select, text

from app.services.db_service import _tid, session

log = logging.getLogger("app.message_delivery")

_BATCH = 200
_ASYNC_THRESHOLD = 500
_MAX_ATTEMPTS = 8
_LEASE_SECONDS = 120


def _utc_now() -> datetime:
    from app.core.timeutil import utc_now_naive
    return utc_now_naive()


def _backoff(attempt: int) -> int:
    return min(3600, 30 * (2 ** max(0, attempt - 1)))


def deliver_campaign_batch(campaign_id: int, user_ids: list[int], *,
                           start: int = 0, batch_size: int = _BATCH,
                           finalize_campaign: bool = True) -> dict:
    """向 user_ids[start:start+batch_size] 写入个人消息；返回进度。

    finalize_campaign=False：作业切片投递时不把整单标 PUBLISHED（由 claim 收口）。
    """
    from app.models import MessageCampaign, UnifiedMessage

    with session() as db:
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == int(campaign_id),
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            return {"ok": False, "reason": "NOT_FOUND", "written": 0, "done": True}

        chunk = user_ids[start:start + batch_size]
        written = 0
        now = _utc_now()
        ack_deadline = getattr(camp, "ack_deadline_at", None)
        for uid in chunk:
            exists = db.scalar(select(UnifiedMessage.id).where(
                UnifiedMessage.tenant_id == _tid(),
                UnifiedMessage.campaign_id == camp.id,
                UnifiedMessage.receiver_user_id == int(uid),
                UnifiedMessage.receiver_context_key == "GLOBAL",
                UnifiedMessage.is_deleted.is_(False),
            ))
            if exists:
                continue
            action_params = dict(camp.action_params_json or {})
            if ack_deadline:
                action_params["ackDeadline"] = ack_deadline.isoformat(sep=" ", timespec="seconds")
            db.add(UnifiedMessage(
                tenant_id=_tid(),
                receiver_id=int(uid),
                receiver_user_id=int(uid),
                receiver_type="UNKNOWN",
                receiver_context_key="GLOBAL",
                campaign_id=camp.id,
                title=camp.title,
                content=(camp.summary or camp.content_plain or "")[:2000],
                message_type=camp.category,
                category=camp.category,
                priority=camp.priority,
                status="UNREAD",
                require_ack=bool(camp.require_ack),
                pinned=bool(camp.pinned) or bool(camp.emergency),
                action_key=camp.action_key,
                action_params_json=action_params or None,
                expire_at=camp.expire_at,
                content_version=int(camp.content_version or 1),
                delivery_status="DELIVERED",
                delivered_at=now,
                sender_org_name_snapshot=camp.org_name_snapshot,
                rendered_content_plain=camp.content_plain if camp.content_mode == "SHARED" else None,
                rendered_title=camp.title,
            ))
            written += 1

        next_start = start + len(chunk)
        done = next_start >= len(user_ids)
        camp.delivered_count = int(camp.delivered_count or 0) + written
        if finalize_campaign:
            if done:
                camp.status = "PUBLISHED" if int(camp.failure_count or 0) == 0 else "PARTIAL_FAILED"
                camp.published_at = camp.published_at or now
            else:
                camp.status = "PUBLISHING"
        elif camp.status not in ("PUBLISHED", "PARTIAL_FAILED", "WITHDRAWN", "EXPIRED"):
            camp.status = "PUBLISHING"
        camp.version = int(camp.version or 0) + 1
        db.commit()
        return {
            "ok": True,
            "written": written,
            "nextStart": next_start,
            "done": done,
            "status": camp.status,
            "deliveredCount": camp.delivered_count,
            "recipientCount": camp.recipient_count,
        }


def deliver_campaign_all(campaign_id: int, user_ids: list[int]) -> dict:
    """同步分批投递（小规模）；大名单请用 enqueue。"""
    start = 0
    total_written = 0
    last: dict = {"ok": True, "done": True, "status": "PUBLISHED"}
    while True:
        last = deliver_campaign_batch(campaign_id, user_ids, start=start)
        if not last.get("ok"):
            return last
        total_written += int(last.get("written") or 0)
        if last.get("done"):
            break
        start = int(last["nextStart"])
    last["written"] = total_written
    return last


def enqueue_campaign_delivery_in_db(db, camp, user_ids: list[int], *,
                                    batch_size: int = _BATCH) -> dict:
    """在调用方事务内创建投递作业（不 commit、不自增 version）。

    状态/version 由调用方负责；本函数只负责落 DeliveryJob，保证可恢复。
    """
    from app.models import MessageDeliveryJob
    from sqlalchemy import func

    ids = [int(x) for x in (user_ids or []) if x]
    camp.recipient_count = len(ids)
    camp.delivery_mode = "ASYNC"
    camp.published_at = camp.published_at or _utc_now()
    if camp.status not in ("PUBLISHING", "PUBLISHED"):
        camp.status = "PUBLISHING"
    if not ids:
        camp.status = "PUBLISHED"
        return {"ok": True, "jobCount": 0, "recipientCount": 0, "async": True}

    existing = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(
        MessageDeliveryJob.tenant_id == int(camp.tenant_id),
        MessageDeliveryJob.campaign_id == int(camp.id),
        MessageDeliveryJob.is_deleted.is_(False),
    )) or 0
    if existing:
        return {"ok": True, "jobCount": int(existing), "recipientCount": len(ids),
                "async": True, "idempotent": True}

    jobs = 0
    for i in range(0, len(ids), batch_size):
        slice_ids = ids[i:i + batch_size]
        db.add(MessageDeliveryJob(
            tenant_id=int(camp.tenant_id),
            campaign_id=int(camp.id),
            cursor_start=i,
            batch_size=batch_size,
            status="PENDING",
            recipient_slice_json=slice_ids,
            created_by=0,
        ))
        jobs += 1
    db.flush()
    return {"ok": True, "jobCount": jobs, "recipientCount": len(ids), "async": True}


def enqueue_campaign_delivery(campaign_id: int, user_ids: list[int], *,
                              batch_size: int = _BATCH) -> dict:
    """切片写入投递作业；独立会话入口（会 bump version 一次）。"""
    from app.models import MessageCampaign

    ids = [int(x) for x in (user_ids or []) if x]
    with session() as db:
        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == int(campaign_id),
            MessageCampaign.tenant_id == _tid(),
            MessageCampaign.is_deleted.is_(False),
        ))
        if not camp:
            return {"ok": False, "jobCount": 0}
        if camp.status not in ("PUBLISHING", "PUBLISHED"):
            camp.status = "PUBLISHING"
            camp.version = int(camp.version or 0) + 1
        result = enqueue_campaign_delivery_in_db(db, camp, ids, batch_size=batch_size)
        db.commit()
        return result


def should_async(user_ids: list[int], *, force: bool = False) -> bool:
    if force:
        return True
    return len(user_ids or []) >= _ASYNC_THRESHOLD


def accept_and_deliver(campaign_id: int, user_ids: list[int], *,
                       force_async: bool = False,
                       already_enqueued: bool = False) -> dict:
    """统一入口：必须先有 DeliveryJob，再尽力内联消费。

    already_enqueued=True：调用方已同事务落作业；此处只 claim，失败不影响已提交受理。
    force_async 保留兼容；同步路径也一律落作业，禁止 commit-then-deliver。
    """
    _ = force_async
    if already_enqueued:
        enq = {"ok": True, "jobCount": None, "recipientCount": len(user_ids or []), "async": True}
    else:
        enq = enqueue_campaign_delivery(campaign_id, user_ids)
    processed = claim_and_process_delivery_jobs(limit=5, worker_id="inline-publish")
    return {
        "status": "PUBLISHING",
        "async": True,
        "jobCount": enq.get("jobCount"),
        "recipientCount": len(user_ids or []),
        "deliveredCount": 0,
        "inlineProcessed": processed,
    }


def claim_and_process_delivery_jobs(*, limit: int = 10, worker_id: str = "scheduler",
                                    lease_seconds: int = _LEASE_SECONDS) -> int:
    """领取 PENDING/RETRY_WAIT 作业并投递；返回成功批次数。"""
    from app.models import MessageCampaign, MessageDeliveryJob

    now = _utc_now()
    done = 0
    claimed_ids: list[int] = []
    with session() as db:
        # 优先 SKIP LOCKED（MySQL 8+）
        try:
            rows = db.execute(text(
                "SELECT id FROM t_message_delivery_job "
                "WHERE tenant_id=:tid AND is_deleted=0 "
                "AND status IN ('PENDING','RETRY_WAIT') "
                "AND (next_retry_at IS NULL OR next_retry_at<=:now) "
                "ORDER BY id ASC LIMIT :lim "
                "FOR UPDATE SKIP LOCKED"
            ), {"tid": _tid(), "now": now, "lim": limit}).fetchall()
            ids = [int(r[0]) for r in rows]
        except Exception:  # noqa: BLE001
            rows = db.scalars(
                select(MessageDeliveryJob).where(
                    MessageDeliveryJob.tenant_id == _tid(),
                    MessageDeliveryJob.is_deleted.is_(False),
                    MessageDeliveryJob.status.in_(("PENDING", "RETRY_WAIT")),
                    or_(
                        MessageDeliveryJob.next_retry_at.is_(None),
                        MessageDeliveryJob.next_retry_at <= now,
                    ),
                ).order_by(MessageDeliveryJob.id.asc()).limit(limit)
            ).all()
            ids = [int(r.id) for r in rows]

        for jid in ids:
            job = db.get(MessageDeliveryJob, jid)
            if not job:
                continue
            if job.lease_expires_at and job.lease_expires_at > now and job.locked_by != worker_id:
                continue
            job.status = "PROCESSING"
            job.locked_by = worker_id
            job.locked_at = now
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.attempt_count = int(job.attempt_count or 0) + 1
            claimed_ids.append(jid)
        if claimed_ids:
            db.commit()

    for jid in claimed_ids:
        with session() as db:
            job = db.get(MessageDeliveryJob, jid)
            if not job or job.status != "PROCESSING":
                continue
            try:
                slice_ids = list(job.recipient_slice_json or [])
                result = deliver_campaign_batch(
                    int(job.campaign_id), slice_ids, start=0,
                    batch_size=max(int(job.batch_size or _BATCH), len(slice_ids) or 1),
                    finalize_campaign=False)
                # batch 在独立 session 提交；此处刷新 job 行状态
                job.written_count = int(result.get("written") or 0)
                job.status = "SUCCEEDED"
                job.last_error_code = None
                job.locked_by = None
                job.lease_expires_at = None
                # 若全部 job 完成则收口 campaign
                pending = db.scalar(select(MessageDeliveryJob.id).where(
                    MessageDeliveryJob.tenant_id == _tid(),
                    MessageDeliveryJob.campaign_id == job.campaign_id,
                    MessageDeliveryJob.is_deleted.is_(False),
                    MessageDeliveryJob.status.in_(("PENDING", "PROCESSING", "RETRY_WAIT")),
                    MessageDeliveryJob.id != job.id,
                ))
                camp = db.get(MessageCampaign, job.campaign_id)
                if camp and not pending:
                    dead = db.scalar(select(MessageDeliveryJob.id).where(
                        MessageDeliveryJob.tenant_id == _tid(),
                        MessageDeliveryJob.campaign_id == job.campaign_id,
                        MessageDeliveryJob.status == "DEAD",
                        MessageDeliveryJob.is_deleted.is_(False),
                    ))
                    camp.status = "PARTIAL_FAILED" if dead else "PUBLISHED"
                    camp.published_at = camp.published_at or _utc_now()
                    camp.version = int(camp.version or 0) + 1
                db.commit()
                done += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                with session() as db2:
                    job2 = db2.get(MessageDeliveryJob, jid)
                    if not job2:
                        continue
                    attempt = int(job2.attempt_count or 1)
                    job2.last_error_code = type(exc).__name__[:80]
                    job2.locked_by = None
                    job2.lease_expires_at = None
                    if attempt >= _MAX_ATTEMPTS:
                        job2.status = "DEAD"
                        camp = db2.get(MessageCampaign, job2.campaign_id)
                        if camp:
                            camp.failure_count = int(camp.failure_count or 0) + 1
                            camp.status = "PARTIAL_FAILED"
                            camp.version = int(camp.version or 0) + 1
                    else:
                        job2.status = "RETRY_WAIT"
                        job2.next_retry_at = _utc_now() + timedelta(seconds=_backoff(attempt))
                    db2.commit()
                log.exception("delivery job failed id=%s", jid)
    return done


def list_dead_delivery_jobs(*, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
    from app.models import MessageDeliveryJob
    from app.services.db_service import _iso
    with session() as db:
        conds = [
            MessageDeliveryJob.tenant_id == _tid(),
            MessageDeliveryJob.is_deleted.is_(False),
            MessageDeliveryJob.status == "DEAD",
        ]
        from sqlalchemy import func
        total = db.scalar(select(func.count()).select_from(MessageDeliveryJob).where(*conds)) or 0
        rows = db.scalars(
            select(MessageDeliveryJob).where(*conds)
            .order_by(MessageDeliveryJob.id.desc())
            .offset(max(0, (page - 1) * page_size)).limit(page_size)
        ).all()
        items = [{
            "jobId": str(r.id),
            "kind": "DELIVERY_JOB",
            "campaignId": str(r.campaign_id),
            "status": r.status,
            "attemptCount": r.attempt_count,
            "lastError": r.last_error_code,
            "cursorStart": r.cursor_start,
            "updatedAt": _iso(r.updated_at) if r.updated_at else None,
        } for r in rows]
        return items, int(total)


def retry_dead_delivery_job(job_id: int) -> dict:
    from app.models import MessageDeliveryJob
    with session() as db:
        job = db.scalar(select(MessageDeliveryJob).where(
            MessageDeliveryJob.id == int(job_id),
            MessageDeliveryJob.tenant_id == _tid(),
            MessageDeliveryJob.is_deleted.is_(False),
        ))
        if not job:
            from app.core.exceptions import not_found
            raise not_found("投递作业不存在")
        if job.status != "DEAD":
            from app.core.exceptions import AppException
            raise AppException("DATA_CONFLICT", "仅死信可重试")
        job.status = "PENDING"
        job.next_retry_at = None
        job.last_error_code = None
        job.attempt_count = 0
        job.version = int(job.version or 0) + 1
        db.commit()
        return {"jobId": str(job.id), "status": "PENDING"}
