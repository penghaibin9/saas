"""DB 幂等 fallback 必须与 Redis 一样按 TTL 过期，不能永久重放历史成功结果。"""
from __future__ import annotations

from datetime import datetime, timedelta

TID = 1000000000000000001


def test_db_idempotency_success_expires_and_key_can_be_reused(db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.core.idempotency import _begin_db, abort, finish
    from app.db.session import get_sessionmaker
    from app.models.idempotency import IdempotencyRecord

    user = {"tenantId": str(TID), "userId": "a3-idempotency-test"}
    operation = "a3-repeatable-followup"
    key = "employment-a3-fixed-payload-key"
    previous = get_tenant()
    set_tenant({"tenantId": str(TID)})
    try:
        cached, handle = _begin_db(user, operation, key, {"content": "第一次"})
        assert cached is None and handle is not None and handle[0].startswith("db:")
        row_id = int(handle[0].split(":", 2)[1])
        finish(handle, {"id": "first"})

        cached, replay_handle = _begin_db(user, operation, key, {"content": "第一次"})
        assert cached == {"id": "first"} and replay_handle is None

        db = get_sessionmaker()()
        try:
            row = db.get(IdempotencyRecord, row_id)
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

        # TTL 过期后不仅同内容可重做，连同一个 raw key 的新 payload 也应按新动作重新预占。
        cached, new_handle = _begin_db(user, operation, key, {"content": "第二次"})
        assert cached is None and new_handle is not None
        abort(new_handle)
    finally:
        set_tenant(previous)
