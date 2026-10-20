"""实习批次参与人规则懒初始化并发回归。

S1 production runtime 在两个 uvicorn worker 下真实撞出过：两个请求同时读取到规则不存在，
随后一起 INSERT，同一 (tenant_id, batch_id) 唯一键让其中一个请求以 MySQL 1062 / HTTP 500
失败。这里直接用真实 MySQL 8 线程同时读取同一批次规则，守住“只创建一行且所有调用成功”。
"""
from __future__ import annotations

import threading
import uuid

TID = 1000000000000000001


def _ctx() -> None:
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "intern-participant-concurrency",
        "tenantId": str(TID),
        "realName": "实习管理员",
        "currentRoleCode": "SCHOOL_ADMIN",
    })


def test_concurrent_get_rule_creates_exactly_one_row(db_mode):
    """真实 MySQL 并发初始化：8 个调用全部成功，最终只有一条规则。"""
    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipBatchScopeRule
    from app.modules.internship.services import internship_participant_service as svc

    _ctx()
    suffix = uuid.uuid4().hex[:10]
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name=f"参与规则并发-{suffix}",
            batch_no=f"IPRC-{suffix}",
            status="DRAFT",
        )
        db.add(batch)
        db.commit()
        batch_id = int(batch.id)
    finally:
        db.close()

    workers = 8
    barrier = threading.Barrier(workers)
    lock = threading.Lock()
    results: list[dict] = []
    errors: list[str] = []

    def _read_rule() -> None:
        _ctx()
        try:
            barrier.wait(timeout=30)
            out = svc.get_rule(batch_id)
            with lock:
                results.append(out)
        except Exception as exc:  # noqa: BLE001 - 并发异常必须完整收集，不能静默吞掉
            with lock:
                errors.append(repr(exc))

    threads = [threading.Thread(target=_read_rule) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    alive = [thread.name for thread in threads if thread.is_alive()]
    assert not alive, f"并发读取发生阻塞/死锁：{alive}"
    assert not errors, f"并发读取参与人规则出现异常：{errors}"
    assert len(results) == workers, f"只有 {len(results)} 个调用成功：{results}"
    assert all(x["batchId"] == str(batch_id) for x in results)
    assert all(x["rule"] == {} for x in results)

    db = get_sessionmaker()()
    try:
        count = db.scalar(select(func.count()).select_from(InternshipBatchScopeRule).where(
            InternshipBatchScopeRule.tenant_id == TID,
            InternshipBatchScopeRule.batch_id == batch_id,
        ))
        rows = db.scalars(select(InternshipBatchScopeRule).where(
            InternshipBatchScopeRule.tenant_id == TID,
            InternshipBatchScopeRule.batch_id == batch_id,
        )).all()
        assert int(count or 0) == 1, f"同一批次产生了 {count} 条规则"
        assert len(rows) == 1 and rows[0].is_deleted is False
        assert rows[0].rule_json == {}
    finally:
        db.close()
