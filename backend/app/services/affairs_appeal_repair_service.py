"""异议/申诉待办与结果消息的持久化补偿队列。

不新增业务表，复用现有 IdempotencyRecord 保存有限期修复任务。教师GET工作台不写库；
补偿由申诉写操作顺带小批处理，或由受保护的维护POST显式触发。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.services.db_service import _tid, session

log = logging.getLogger(__name__)
_OPERATION = "AFFAIRS_APPEAL_REPAIR"
_MAX_ATTEMPTS = 8


def _key(todo_type: str, row_id: int, stage: str) -> str:
    return hashlib.sha256(f"{todo_type}:{int(row_id)}:{stage}".encode("utf-8")).hexdigest()


def enqueue(todo_type: str, row_id: int, stage: str, exc: Exception | None = None) -> None:
    from app.models import IdempotencyRecord

    payload = {
        "todoType": str(todo_type), "rowId": int(row_id), "stage": str(stage),
        "attempts": 0, "lastError": type(exc).__name__ if exc else "",
    }
    key_hash = _key(todo_type, row_id, stage)
    try:
        with session() as db:
            existing = db.scalars(select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == _tid(),
                IdempotencyRecord.user_id == "system",
                IdempotencyRecord.operation == _OPERATION,
                IdempotencyRecord.key_hash == key_hash,
            ).with_for_update()).first()
            if existing:
                if existing.state != "COMPLETED":
                    previous = existing.response_json if isinstance(existing.response_json, dict) else {}
                    payload["attempts"] = int(previous.get("attempts") or 0)
                    existing.response_json = payload
                    existing.state = "PENDING"
                    existing.expires_at = datetime.utcnow() + timedelta(days=30)
                db.commit()
                return
            db.add(IdempotencyRecord(
                tenant_id=_tid(), user_id="system", operation=_OPERATION,
                key_hash=key_hash, fingerprint=key_hash,
                state="PENDING", response_json=payload,
                expires_at=datetime.utcnow() + timedelta(days=30),
            ))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    except Exception:  # noqa: BLE001 - 补偿入队不得反向覆盖已完成业务
        log.exception("failed to enqueue appeal repair")


def _claim(limit: int) -> list[dict]:
    from app.models import IdempotencyRecord

    now = datetime.utcnow()
    with session() as db:
        rows = db.scalars(select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == _tid(),
            IdempotencyRecord.user_id == "system",
            IdempotencyRecord.operation == _OPERATION,
            IdempotencyRecord.state.in_(("PENDING", "FAILED")),
            IdempotencyRecord.expires_at > now,
        ).order_by(IdempotencyRecord.id).with_for_update(skip_locked=True).limit(limit)).all()
        claimed = []
        for row in rows:
            payload = row.response_json if isinstance(row.response_json, dict) else {}
            attempts = int(payload.get("attempts") or 0)
            if attempts >= _MAX_ATTEMPTS:
                row.state = "DEAD"
                continue
            row.state = "PROCESSING"
            payload["attempts"] = attempts + 1
            row.response_json = payload
            claimed.append({"id": int(row.id), **payload})
        db.commit()
        return claimed


def _finish(record_id: int, ok: bool, error: str = "") -> None:
    from app.models import IdempotencyRecord

    with session() as db:
        row = db.get(IdempotencyRecord, int(record_id))
        if not row or row.tenant_id != _tid() or row.operation != _OPERATION:
            return
        payload = row.response_json if isinstance(row.response_json, dict) else {}
        if error:
            payload["lastError"] = error[:120]
        row.response_json = payload
        row.state = "COMPLETED" if ok else (
            "DEAD" if int(payload.get("attempts") or 0) >= _MAX_ATTEMPTS else "FAILED"
        )
        db.commit()


def repair_pending(limit: int = 20) -> dict:
    from app.services import affairs_appeal_todo_service as todo

    limit = min(100, max(1, int(limit or 20)))
    claimed = _claim(limit)
    repaired = failed = 0
    for item in claimed:
        try:
            stage = str(item.get("stage") or "")
            todo_type = str(item.get("todoType") or "")
            row_id = int(item.get("rowId") or 0)
            if stage == "TODO_SYNC":
                ok = bool(todo._sync_todo_after_commit(todo_type, row_id))
            elif stage in ("RESULT_NOTICE", "OUTBOX_DRAIN"):
                ok = bool(todo._result_notice(todo_type, row_id))
            else:
                ok = False
            _finish(item["id"], ok, "" if ok else "repair returned false")
            repaired += int(ok)
            failed += int(not ok)
        except Exception as exc:  # noqa: BLE001
            _finish(item["id"], False, type(exc).__name__)
            failed += 1
    return {"claimed": len(claimed), "repaired": repaired, "failed": failed}


def install() -> None:
    from app.services import affairs_appeal_todo_service as todo

    original = todo._record_sync_failure

    def record_sync_failure(todo_type, row_id, stage, exc):
        original(todo_type, row_id, stage, exc)
        if row_id:
            enqueue(todo_type, int(row_id), stage, exc)

    todo._record_sync_failure = record_sync_failure

    # 每次异议/申诉写操作前小批清理历史补偿；失败不阻塞当前业务。
    for name in ("_sync_todo_after_commit", "_result_notice"):
        original_fn = getattr(todo, name)

        def wrapper(*args, __original=original_fn, **kwargs):
            try:
                repair_pending(limit=5)
            except Exception:  # noqa: BLE001
                log.exception("background appeal repair failed")
            return __original(*args, **kwargs)

        setattr(todo, name, wrapper)
