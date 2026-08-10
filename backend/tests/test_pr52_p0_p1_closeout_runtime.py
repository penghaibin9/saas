"""PR #52 合并前 P0/P1 最终收口：真 MySQL 并发 + 关键生产合同。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest

from app.core.exceptions import AppException


ROOT = Path(__file__).resolve().parents[2]
TID = 1000000000000000001


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _db_row_id(handle) -> int:
    return int(str(handle[0]).split(":", 2)[1])


def test_db_idempotency_expired_key_concurrent_reclaim_has_one_winner(db_mode):
    """真 MySQL：TTL 过期后两个并发请求只能有一个重新获得 PROCESSING 所有权。"""
    from app.core.context import get_tenant, set_tenant
    from app.core.idempotency import _begin_db, abort, finish
    from app.db.session import get_sessionmaker
    from app.models.idempotency import IdempotencyRecord

    user = {"tenantId": str(TID), "userId": "pr52-concurrent-reclaim"}
    operation = "pr52-concurrent-reclaim"
    key = "pr52-concurrent-reclaim-key"
    previous = get_tenant()
    set_tenant({"tenantId": str(TID)})
    try:
        cached, first = _begin_db(user, operation, key, {"value": "v1"})
        assert cached is None and first is not None
        row_id = _db_row_id(first)
        finish(first, {"result": "first"})

        db = get_sessionmaker()()
        try:
            row = db.get(IdempotencyRecord, row_id)
            assert row is not None
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

        barrier = Barrier(2)

        def reclaim():
            worker_previous = get_tenant()
            set_tenant({"tenantId": str(TID)})
            try:
                barrier.wait(timeout=10)
                try:
                    value, handle = _begin_db(user, operation, key, {"value": "v2"})
                    return ("ACQUIRED", value, handle)
                except AppException as exc:
                    return ("REJECTED", exc.code, None)
            finally:
                set_tenant(worker_previous)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _x: reclaim(), range(2)))

        acquired = [x for x in results if x[0] == "ACQUIRED"]
        rejected = [x for x in results if x[0] == "REJECTED"]
        assert len(acquired) == 1, results
        assert len(rejected) == 1, results
        assert rejected[0][1] == "DATA_CONFLICT"
        assert acquired[0][2] is not None
        abort(acquired[0][2])
    finally:
        set_tenant(previous)


def test_db_idempotency_stale_finisher_cannot_overwrite_reclaimed_owner(db_mode):
    """真 MySQL：旧执行器在 TTL 后迟到 finish，不得覆盖新 reservation 的结果。"""
    from app.core.context import get_tenant, set_tenant
    from app.core.idempotency import _begin_db, finish
    from app.db.session import get_sessionmaker
    from app.models.idempotency import IdempotencyRecord

    user = {"tenantId": str(TID), "userId": "pr52-stale-finisher"}
    operation = "pr52-stale-finisher"
    key = "pr52-stale-finisher-key"
    previous = get_tenant()
    set_tenant({"tenantId": str(TID)})
    try:
        cached, stale_handle = _begin_db(user, operation, key, {"value": "same"})
        assert cached is None and stale_handle is not None
        row_id = _db_row_id(stale_handle)

        db = get_sessionmaker()()
        try:
            row = db.get(IdempotencyRecord, row_id)
            assert row is not None
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

        cached, new_handle = _begin_db(user, operation, key, {"value": "same"})
        assert cached is None and new_handle is not None
        new_token = str(new_handle[0]).split(":", 2)[2]

        # 旧 owner 的迟到 finish 必须被 ownership guard 丢弃。
        finish(stale_handle, {"owner": "stale"})
        db = get_sessionmaker()()
        try:
            row = db.get(IdempotencyRecord, row_id)
            assert row.state == "PROCESSING"
            assert row.result_json == {"reservationToken": new_token}
        finally:
            db.close()

        finish(new_handle, {"owner": "new"})
        db = get_sessionmaker()()
        try:
            row = db.get(IdempotencyRecord, row_id)
            assert row.state == "SUCCESS"
            assert row.result_json == {"owner": "new"}
        finally:
            db.close()
    finally:
        set_tenant(previous)


def test_approval_batch_and_export_require_real_client_idempotency_keys():
    routes = read("backend/app/api/v1/approval.py")
    pc = read("frontend/src/modules/approval/api/approval.api.js")

    assert "def _require_idempotency_key" in routes
    batch = routes.split('@router.post("/batch"', 1)[1].split('@router.post("/export"', 1)[0]
    export = routes.split('@router.post("/export"', 1)[1].split('@router.get("/export/{task_id}"', 1)[0]
    assert "_require_idempotency_key(idempotency_key)" in batch
    assert "_require_idempotency_key(idempotency_key)" in export
    assert "'Idempotency-Key': key" in pc
    assert "idempotentPost('batch-approve'" in pc
    assert "idempotentPost('batch-return'" in pc
    assert "idempotentPost('batch-transfer'" in pc
    assert "idempotentPost('export'" in pc


def test_approval_summary_and_filters_are_database_first():
    runtime = read("backend/app/services/approval_runtime_service.py")
    base = read("backend/app/services/approval_service.py")
    routes = read("backend/app/api/v1/approval.py")
    pc = read("frontend/src/modules/approval/api/approval.api.js")

    summary = runtime.split("def summary(", 1)[1].split("def approve(", 1)[0]
    assert ".limit(500)" not in summary
    assert ".group_by(WorkflowInstance.source_biz_type)" in summary
    assert "overdue_count = _count" in summary
    assert "near_count = _count" in summary
    assert ".limit(10)" in summary

    db_list = base.split("def _db_list(", 1)[1].split("def list_tasks(", 1)[0]
    assert "WorkflowTask.deadline_at < now" in db_list
    assert "WorkflowTask.created_at >= date_start" in db_list
    assert db_list.index("WorkflowTask.deadline_at < now") < db_list.index("count_q =")
    assert db_list.index("WorkflowTask.created_at >= date_start") < db_list.index("count_q =")
    assert db_list.index("count_q =") < db_list.index(".offset(")

    assert "urgency: str | None" in routes
    assert "submitDate: str | None" in routes
    assert "urgency: params.urgency" in pc
    assert "submitDate: params.submitDate" in pc
    assert "list = list.filter((x) => x.urgency" not in pc


def test_transfer_candidates_and_mobile_actions_share_persisted_policy():
    routes = read("backend/app/api/v1/approval.py")
    guard = read("backend/app/services/approval_production_guard.py")
    mobile = read("backend/app/services/approval_mobile_query_service.py")
    pc = read("frontend/src/modules/approval/api/approval.api.js")

    assert '@router.get("/tasks/{task_id}/transfer-targets"' in routes
    assert '@router.get("/transfer-targets"' not in routes
    targets = guard.split("def guarded_transfer_targets(", 1)[1].split("runtime_module.get_task", 1)[0]
    assert "WorkflowTask.id == task_id_int" in targets
    assert "db_service._assert_task_assignee" in targets
    assert "role_code = _assert_transfer_policy" in targets
    assert "assert_transfer_target_scope(" in targets
    assert "Role.role_code == role_code" in targets

    assert "def persisted_allowed_actions(" in guard
    assert "if actions is None else actions" in guard
    assert "persisted_allowed_actions(" in mobile
    assert "allowed_actions=persisted_allowed_actions" in mobile
    assert "request('/approvals/transfer-targets')" not in pc
    assert "/transfer-targets`" in pc


def test_empty_server_allowed_actions_cannot_be_reexpanded(monkeypatch):
    """授权层返回 [] 时，persisted policy 只能继续收窄，绝不能重新放大为四动作。"""
    from types import SimpleNamespace
    from app.services import approval_production_guard as guard

    task = SimpleNamespace(status="PENDING", tenant_id=TID, node_code="N1")
    inst = SimpleNamespace(workflow_code="WF")
    definition = SimpleNamespace(allow_reject=True, allow_transfer=True)
    node = SimpleNamespace(status="ACTIVE", approver_role_code="COUNSELOR")
    monkeypatch.setattr(guard, "_load_policy", lambda *_args, **_kwargs: (definition, node))

    assert guard.persisted_allowed_actions(object(), task, inst, [], tenant_id=TID) == []
