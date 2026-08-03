"""异议/申诉待办与结果消息的持久化补偿队列。

任务写入专用 ``t_affairs_repair_job``，通过租约、退避和 DEAD 状态保证进程
在领取后崩溃时仍可恢复；教师 GET 工作台绝不写库。
"""
from __future__ import annotations

import hashlib
import logging
import socket
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.services.db_service import _tid, session

log = logging.getLogger(__name__)
_MAX_ATTEMPTS = 8
_LEASE_SECONDS = 5 * 60
_WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"
_REPAIRING: ContextVar[bool] = ContextVar("affairs_appeal_repairing", default=False)
_RAW_SYNC = None
_RAW_NOTICE = None


def _key(todo_type: str, row_id: int, stage: str) -> str:
    return hashlib.sha256(f"{todo_type}:{int(row_id)}:{stage}".encode("utf-8")).hexdigest()


def enqueue(todo_type: str, row_id: int, stage: str, exc: Exception | None = None) -> None:
    from app.models import AffairsRepairJob

    now = datetime.utcnow()
    dedup_key = _key(todo_type, row_id, stage)
    try:
        with session() as db:
            row = db.scalars(select(AffairsRepairJob).where(
                AffairsRepairJob.tenant_id == _tid(),
                AffairsRepairJob.dedup_key == dedup_key,
                AffairsRepairJob.is_deleted.is_(False),
            ).with_for_update()).first()
            if row:
                if row.state != "COMPLETED":
                    row.todo_type = str(todo_type)
                    row.source_row_id = int(row_id)
                    row.stage = str(stage)
                    row.state = "PENDING"
                    row.next_run_at = now
                    row.lease_owner = None
                    row.lease_until = None
                    row.last_error = type(exc).__name__ if exc else None
                    row.version = int(row.version or 0) + 1
                db.commit()
                return
            db.add(AffairsRepairJob(
                tenant_id=_tid(), dedup_key=dedup_key,
                todo_type=str(todo_type), source_row_id=int(row_id), stage=str(stage),
                state="PENDING", attempts=0, next_run_at=now,
                last_error=type(exc).__name__ if exc else None,
                payload_json={"todoType": str(todo_type), "rowId": int(row_id), "stage": str(stage)},
            ))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    except Exception:  # noqa: BLE001 - 补偿入队不得反向覆盖已完成业务
        log.exception("failed to enqueue appeal repair")


def _claim(limit: int, *, worker_id: str | None = None, lease_seconds: int = _LEASE_SECONDS) -> list[dict]:
    """原子领取到期任务，并回收 lease_until 已过期的 PROCESSING。"""
    from app.models import AffairsRepairJob

    now = datetime.utcnow()
    worker_id = str(worker_id or _WORKER_ID)
    lease_seconds = max(30, int(lease_seconds or _LEASE_SECONDS))
    with session() as db:
        runnable = or_(
            and_(
                AffairsRepairJob.state.in_(("PENDING", "FAILED")),
                AffairsRepairJob.next_run_at <= now,
            ),
            and_(
                AffairsRepairJob.state == "PROCESSING",
                AffairsRepairJob.lease_until.is_not(None),
                AffairsRepairJob.lease_until <= now,
            ),
        )
        rows = db.scalars(select(AffairsRepairJob).where(
            AffairsRepairJob.tenant_id == _tid(),
            AffairsRepairJob.is_deleted.is_(False),
            runnable,
        ).order_by(AffairsRepairJob.next_run_at, AffairsRepairJob.id)
         .with_for_update(skip_locked=True).limit(limit)).all()
        claimed = []
        for row in rows:
            if int(row.attempts or 0) >= _MAX_ATTEMPTS:
                row.state = "DEAD"
                row.lease_owner = None
                row.lease_until = None
                continue
            row.state = "PROCESSING"
            row.attempts = int(row.attempts or 0) + 1
            row.lease_owner = worker_id
            row.lease_until = now + timedelta(seconds=lease_seconds)
            row.version = int(row.version or 0) + 1
            claimed.append({
                "id": int(row.id), "todoType": row.todo_type,
                "rowId": int(row.source_row_id), "stage": row.stage,
                "attempts": int(row.attempts), "leaseOwner": worker_id,
                "leaseUntil": row.lease_until.isoformat(),
            })
        db.commit()
        return claimed


def _finish(record_id: int, ok: bool, error: str = "", *, lease_owner: str | None = None) -> None:
    from app.models import AffairsRepairJob

    now = datetime.utcnow()
    with session() as db:
        row = db.get(AffairsRepairJob, int(record_id))
        if not row or row.tenant_id != _tid() or row.is_deleted:
            return
        if lease_owner and row.lease_owner != lease_owner:
            return
        row.lease_owner = None
        row.lease_until = None
        row.last_error = error[:500] if error else None
        if ok:
            row.state = "COMPLETED"
            row.next_run_at = now
        elif int(row.attempts or 0) >= _MAX_ATTEMPTS:
            row.state = "DEAD"
            row.next_run_at = now
        else:
            row.state = "FAILED"
            # 1m, 2m, 4m... capped at 6h.
            delay = min(6 * 3600, 60 * (2 ** max(0, int(row.attempts or 1) - 1)))
            row.next_run_at = now + timedelta(seconds=delay)
        row.version = int(row.version or 0) + 1
        db.commit()


def repair_metrics() -> dict:
    from app.models import AffairsRepairJob

    now = datetime.utcnow()
    with session() as db:
        grouped = dict(db.execute(select(
            AffairsRepairJob.state, func.count(AffairsRepairJob.id),
        ).where(
            AffairsRepairJob.tenant_id == _tid(),
            AffairsRepairJob.is_deleted.is_(False),
        ).group_by(AffairsRepairJob.state)).all())
        oldest = db.scalar(select(func.min(AffairsRepairJob.created_at)).where(
            AffairsRepairJob.tenant_id == _tid(),
            AffairsRepairJob.state.in_(("PENDING", "FAILED", "PROCESSING")),
            AffairsRepairJob.is_deleted.is_(False),
        ))
        return {
            "pending": int(grouped.get("PENDING", 0) or 0),
            "failed": int(grouped.get("FAILED", 0) or 0),
            "processing": int(grouped.get("PROCESSING", 0) or 0),
            "dead": int(grouped.get("DEAD", 0) or 0),
            "oldestAgeSeconds": max(0, int((now - oldest).total_seconds())) if oldest else 0,
        }


def list_jobs(*, state: str = "", page: int = 1, page_size: int = 20) -> dict:
    """维护台分页查看任务；仅返回补偿元数据，不返回申诉正文。"""
    from app.models import AffairsRepairJob

    normalized = str(state or "").strip().upper()
    allowed = {"PENDING", "FAILED", "PROCESSING", "DEAD", "COMPLETED"}
    if normalized and normalized not in allowed:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "补偿任务状态非法")
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    with session() as db:
        conds = [
            AffairsRepairJob.tenant_id == _tid(),
            AffairsRepairJob.is_deleted.is_(False),
        ]
        if normalized:
            conds.append(AffairsRepairJob.state == normalized)
        total = int(db.scalar(select(func.count()).select_from(AffairsRepairJob).where(*conds)) or 0)
        rows = db.scalars(
            select(AffairsRepairJob).where(*conds)
            .order_by(AffairsRepairJob.next_run_at, AffairsRepairJob.id)
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return {
            "page": page, "pageSize": page_size, "total": total,
            "hasMore": page * page_size < total,
            "items": [{
                "jobId": str(row.id), "todoType": row.todo_type,
                "sourceRowId": str(row.source_row_id), "stage": row.stage,
                "state": row.state, "attempts": int(row.attempts or 0),
                "nextRunAt": row.next_run_at.isoformat() if row.next_run_at else None,
                "leaseOwner": row.lease_owner,
                "leaseUntil": row.lease_until.isoformat() if row.lease_until else None,
                "lastError": row.last_error or "",
                "version": int(row.version or 0),
            } for row in rows],
        }


def requeue_dead(record_id: int, *, expected_version: int) -> dict:
    """人工重投 DEAD 任务；通过版本锁防止覆盖其他管理员的处理。"""
    from app.core.exceptions import AppException, not_found
    from app.models import AffairsRepairJob

    now = datetime.utcnow()
    with session() as db:
        row = db.scalars(select(AffairsRepairJob).where(
            AffairsRepairJob.id == int(record_id),
            AffairsRepairJob.tenant_id == _tid(),
            AffairsRepairJob.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("补偿任务不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "补偿任务已被其他管理员处理，请刷新后重试")
        if row.state != "DEAD":
            raise AppException("DATA_CONFLICT", "只有 DEAD 任务可以人工重投")
        row.state = "PENDING"
        row.attempts = 0
        row.next_run_at = now
        row.lease_owner = None
        row.lease_until = None
        row.last_error = None
        row.version = int(row.version or 0) + 1
        db.commit()
        return {
            "jobId": str(row.id), "state": row.state, "attempts": row.attempts,
            "nextRunAt": row.next_run_at.isoformat(), "version": int(row.version or 0),
        }

def _ensure_bindings() -> None:
    global _RAW_SYNC, _RAW_NOTICE
    if _RAW_SYNC is not None and _RAW_NOTICE is not None:
        return
    from app.services import affairs_appeal_todo_service as todo
    _RAW_SYNC = todo._sync_todo_after_commit
    _RAW_NOTICE = todo._result_notice


def repair_pending(limit: int = 20) -> dict:
    _ensure_bindings()
    if _REPAIRING.get():
        return {"claimed": 0, "repaired": 0, "failed": 0}

    token = _REPAIRING.set(True)
    try:
        limit = min(100, max(1, int(limit or 20)))
        claimed = _claim(limit)
        repaired = failed = 0
        for item in claimed:
            try:
                stage = str(item.get("stage") or "")
                todo_type = str(item.get("todoType") or "")
                row_id = int(item.get("rowId") or 0)
                if stage == "TODO_SYNC":
                    ok = bool(_RAW_SYNC(todo_type, row_id))
                elif stage in ("RESULT_NOTICE", "OUTBOX_DRAIN"):
                    ok = bool(_RAW_NOTICE(todo_type, row_id))
                else:
                    ok = False
                _finish(item["id"], ok, "" if ok else "repair returned false", lease_owner=item.get("leaseOwner"))
                repaired += int(ok)
                failed += int(not ok)
            except Exception as exc:  # noqa: BLE001
                _finish(item["id"], False, type(exc).__name__, lease_owner=item.get("leaseOwner"))
                failed += 1
        return {"claimed": len(claimed), "repaired": repaired, "failed": failed}
    finally:
        _REPAIRING.reset(token)


def install() -> None:
    """兼容初始化：只绑定正式函数引用，不替换任何生产函数对象。"""
    _ensure_bindings()
