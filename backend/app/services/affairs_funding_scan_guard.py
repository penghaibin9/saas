"""包 10：资助公示自动扫描的逐申请事务隔离。

旧实现把最多 200 条到期申请放进同一事务。只要其中一条触发名额或金额额度冲突，
整个事务都会回滚，已经成功占位的申请也会被撤销，后续扫描会重复失败。
本守卫先读取候选 ID，再逐条加锁、逐条提交；并发 worker 通过 SKIP LOCKED 互斥，
额度冲突只影响当前申请，不影响同批次其他合法申请。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.services import affairs_funding_service as legacy
from app.services.db_service import _tid, session

_INSTALLED = False
_ORIGINAL_SCAN: Any = None
_QUOTA_CONFLICT_MARKERS = {
    "FUNDING_QUOTA_OR_BUDGET_EXCEEDED",
    "FUNDING_QUOTA_EXCEEDED",
    "FUNDING_AMOUNT_BUDGET_EXCEEDED",
}


def _is_quota_conflict(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc) or exc)
    return any(marker in message for marker in _QUOTA_CONFLICT_MARKERS)


def scan_publicity() -> dict:
    """逐申请确认公示，保证某一条额度冲突不会回滚整批成功项。"""
    from app.models import FundingApplication, FundingBatch

    now = datetime.utcnow()
    tenant_id = _tid()
    candidates: list[int] = []
    skipped_appeal = 0
    invalid_batch = 0

    # 第一阶段只读取候选，不持有跨申请长事务锁。
    with session() as db:
        rows = db.execute(
            select(
                FundingApplication.id,
                FundingApplication.batch_id,
                FundingApplication.publicity_at,
            )
            .where(
                FundingApplication.tenant_id == tenant_id,
                FundingApplication.status == "PUBLICITY",
                FundingApplication.publicity_at.is_not(None),
                FundingApplication.is_deleted.is_(False),
            )
            .order_by(FundingApplication.id)
            .limit(200)
        ).all()
        pending = legacy._pending_appeal_ids(db, [row.id for row in rows])
        batch_ids = {int(row.batch_id) for row in rows if row.batch_id}
        batches = {
            int(batch.id): batch
            for batch in db.scalars(
                select(FundingBatch).where(
                    FundingBatch.tenant_id == tenant_id,
                    FundingBatch.id.in_(batch_ids) if batch_ids else FundingBatch.id == -1,
                    FundingBatch.is_deleted.is_(False),
                )
            ).all()
        }
        for row in rows:
            app_id = int(row.id)
            if app_id in pending:
                skipped_appeal += 1
                continue
            batch = batches.get(int(row.batch_id)) if row.batch_id else None
            if not batch:
                invalid_batch += 1
                continue
            due = row.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
            if due <= now:
                candidates.append(app_id)

    confirmed = 0
    quota_conflict = 0
    stale = 0

    # 第二阶段逐申请独立事务：一条失败不会污染其他申请。
    for app_id in candidates:
        with session() as db:
            application = db.scalars(
                select(FundingApplication)
                .where(
                    FundingApplication.id == app_id,
                    FundingApplication.tenant_id == tenant_id,
                    FundingApplication.status == "PUBLICITY",
                    FundingApplication.is_deleted.is_(False),
                )
                .with_for_update(skip_locked=True)
            ).first()
            if not application:
                stale += 1
                continue

            # 候选读取后可能新产生申诉，正式写入前必须再次核验。
            if legacy._pending_appeal_ids(db, [app_id]):
                skipped_appeal += 1
                continue

            batch = db.get(FundingBatch, int(application.batch_id)) if application.batch_id else None
            if not batch or batch.is_deleted or int(batch.tenant_id) != int(tenant_id):
                invalid_batch += 1
                continue
            due = application.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
            if due > datetime.utcnow():
                stale += 1
                continue

            try:
                legacy._grant_one(db, application)
                db.commit()
                confirmed += 1
            except DBAPIError as exc:
                db.rollback()
                if _is_quota_conflict(exc):
                    quota_conflict += 1
                    continue
                raise

    legacy._drain_message_outbox()
    return {
        "count": confirmed,
        "skippedAppeal": skipped_appeal,
        "invalidBatch": invalid_batch,
        "quotaConflict": quota_conflict,
        "stale": stale,
    }


def install() -> None:
    global _INSTALLED, _ORIGINAL_SCAN
    if _INSTALLED:
        return
    _ORIGINAL_SCAN = legacy.scan_publicity
    legacy.scan_publicity = scan_publicity
    _INSTALLED = True
