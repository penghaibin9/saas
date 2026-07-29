"""异议/申诉补偿队列持久化回归测试。"""
from __future__ import annotations


TID = 1000000000000000001


def _set_context():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "db-1",
        "realName": "学校管理员",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TID),
    })


def _clear_context():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def test_appeal_repair_queue_uses_real_result_json_column(db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import IdempotencyRecord
    from app.services import affairs_appeal_repair_service as repair

    _set_context()
    try:
        repair.enqueue(
            "AID_OBJECTION_REVIEW",
            880001,
            "TODO_SYNC",
            RuntimeError("todo unavailable"),
        )

        db = get_sessionmaker()()
        row = db.scalars(select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == TID,
            IdempotencyRecord.operation == repair._OPERATION,
            IdempotencyRecord.key_hash == repair._key(
                "AID_OBJECTION_REVIEW", 880001, "TODO_SYNC"
            ),
        )).first()
        assert row is not None
        assert row.state == "PENDING"
        assert isinstance(row.result_json, dict)
        assert row.result_json["todoType"] == "AID_OBJECTION_REVIEW"
        assert row.result_json["rowId"] == 880001
        assert row.result_json["stage"] == "TODO_SYNC"
        db.close()

        claimed = repair._claim(10)
        item = next(x for x in claimed if x["rowId"] == 880001)
        assert item["attempts"] == 1

        db = get_sessionmaker()()
        claimed_row = db.get(IdempotencyRecord, item["id"])
        assert claimed_row.state == "PROCESSING"
        assert claimed_row.result_json["attempts"] == 1
        db.close()
    finally:
        _clear_context()
