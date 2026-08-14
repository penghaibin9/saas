"""t_audit_outbox 投递语义回归锁。

历史问题：internship_audit_service.add_audit() 自己 db.add 一条 AuditOutbox，
audit_outbox 的 before_flush 监听器看到同一条 InternshipAuditTrail 又 add 一条，
两条 event_id 还不相同 —— 同一个审计事实入队两次，且返回给调用方的 event_id
只对应其中一条，mark_processed 永远处理不掉另一条。

原有测试只断言 event_id 上有唯一约束，抓不到这个缺陷（两条 event_id 本来就不同）。
本文件锁住真正的不变式：一次业务审计 = 恰好一条 outbox 事件，且 id 可被调用方处理。
"""
from __future__ import annotations

from sqlalchemy import func, select


def _count(db) -> int:
    from app.models import AuditOutbox
    return int(db.scalar(select(func.count()).select_from(AuditOutbox)) or 0)


def test_add_audit_enqueues_exactly_one_outbox_event(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AuditOutbox
    from app.modules.internship.services import internship_audit_service as svc

    set_tenant({"tenantId": "1000000000000000001"})
    db = get_sessionmaker()()
    try:
        before = _count(db)
        event_id = svc.add_audit(
            db, target_type="internship", target_id=901, action="TEST_ONCE",
            user={"userId": "db-1", "realName": "测试员"}, reason="回归锁",
        )
        db.commit()

        assert _count(db) == before + 1, "一次 add_audit 必须只入队一条 outbox 事件"
        rows = db.scalars(select(AuditOutbox).where(
            AuditOutbox.event_id == event_id)).all()
        assert len(rows) == 1, "add_audit 返回的 event_id 必须对应真实存在的那一条"
        assert rows[0].event_type == "INTERNSHIP_TEST_ONCE"
        assert rows[0].status == "PENDING"
    finally:
        db.close()
        set_tenant(None)


def test_returned_event_id_can_be_marked_processed(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AuditOutbox
    from app.modules.internship.services import internship_audit_service as svc

    set_tenant({"tenantId": "1000000000000000001"})
    db = get_sessionmaker()()
    try:
        event_id = svc.add_audit(
            db, target_type="internship", target_id=902, action="TEST_ACK",
            user={"userId": "db-1", "realName": "测试员"})
        db.commit()
        svc.mark_processed(db, event_id)
        db.commit()

        # 关键：不能出现"标记完还剩一条永远 PENDING 的孤儿"。
        leftovers = db.scalars(select(AuditOutbox).where(
            AuditOutbox.event_type == "INTERNSHIP_TEST_ACK",
            AuditOutbox.status != "PROCESSED")).all()
        assert leftovers == [], "同一审计事实不得留下未处理的重复事件"
    finally:
        db.close()
        set_tenant(None)


def test_outbox_consumer_drains_pending_events(db_mode):
    """t_audit_outbox 必须有真实消费者，否则事件永远停在 PENDING。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AuditOutbox, SecurityAuditLog
    from app.modules.internship.services import internship_audit_service as svc

    set_tenant({"tenantId": "1000000000000000001"})
    db = get_sessionmaker()()
    try:
        svc.add_audit(db, target_type="internship", target_id=903, action="TEST_DRAIN",
                      user={"userId": "db-1", "realName": "测试员"})
        db.commit()
    finally:
        db.close()

    result = svc.process_pending(limit=100, worker_id="pytest")
    assert result["processed"] >= 1

    db = get_sessionmaker()()
    try:
        pending = db.scalars(select(AuditOutbox).where(
            AuditOutbox.event_type == "INTERNSHIP_TEST_DRAIN",
            AuditOutbox.status == "PENDING")).all()
        assert pending == [], "消费者跑完不应还有 PENDING 事件"
        sunk = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.action == "INTERNSHIP_TEST_DRAIN")).all()
        assert len(sunk) == 1, "事件必须真正落到安全审计表，而不是只改个状态"
    finally:
        db.close()
        set_tenant(None)


def test_external_scheduler_runs_audit_outbox_consumer(monkeypatch):
    """生产 SCHEDULER_MODE=external 时也必须消费审计 outbox。"""
    from scripts import run_scheduled_jobs as scheduler
    from app.modules.internship.services import internship_audit_service as svc

    calls: list[dict] = []
    monkeypatch.setattr(scheduler, "_candidate_tenant_ids", lambda: [])
    monkeypatch.setattr(scheduler, "_refresh_delivery_metrics", lambda: None)
    monkeypatch.setattr(
        svc,
        "process_pending",
        lambda **kwargs: calls.append(kwargs) or {"processed": 0, "failed": 0},
    )

    scheduler.job_delivery_and_outbox()

    assert calls == [{"limit": 80, "worker_id": "scheduler-audit-outbox"}]
