"""A-W1 / A-C1: current-term Authority must be serialized per tenant on real MySQL.

These tests intentionally exercise the canonical writers instead of adding a second
term truth.  The deterministic RED holds the tenant coordination row before starting
a writer: a production-safe writer must wait for that row before it may mutate
``AaTerm.is_current``.  This proves both ``set_current_term`` and ``publish_term`` use
the same tenant-scoped authority boundary.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from sqlalchemy import func, select

from app.modules.academic_affairs.services import academic_affairs_service as svc

TID = 1000000000000000001
NEIGHBOR_TID = 1000000000000000099


def _seed_terms():
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, NEIGHBOR_TID) is None:
            db.add(
                Tenant(
                    id=NEIGHBOR_TID,
                    tenant_code="aa-w1-neighbor",
                    school_name="A-W1 邻租户学校",
                    short_name="A-W1邻校",
                    deploy_mode="SAAS",
                    db_mode="SHARED",
                    status="ACTIVE",
                )
            )
            db.flush()

        current = AaTerm(
            tenant_id=TID,
            year_code="2091-2092",
            term_no=1,
            term_name="A-W1 原当前学期",
            teaching_weeks=17,
            status="PUBLISHED",
            is_current=True,
        )
        target = AaTerm(
            tenant_id=TID,
            year_code="2091-2092",
            term_no=2,
            term_name="A-W1 待切换学期",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        publish_target = AaTerm(
            tenant_id=TID,
            year_code="2092-2093",
            term_no=1,
            term_name="A-W1 待发布学期",
            teaching_weeks=17,
            status="DRAFT",
            is_current=False,
        )
        neighbor = AaTerm(
            tenant_id=NEIGHBOR_TID,
            year_code="2091-2092",
            term_no=1,
            term_name="A-W1 邻租户当前学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        db.add_all([current, target, publish_target, neighbor])
        db.commit()
        return {
            "current": int(current.id),
            "target": int(target.id),
            "publish_target": int(publish_target.id),
            "neighbor": int(neighbor.id),
        }
    finally:
        db.close()


def _hold_tenant_lock(tenant_id: int):
    """Return a live transaction holding the canonical tenant coordination row."""
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    db.begin()
    locked = db.scalar(
        select(Tenant.id).where(Tenant.id == tenant_id).with_for_update()
    )
    assert int(locked) == tenant_id
    return db


def _assert_writer_waits_for_tenant_lock(monkeypatch, action: str, invoke):
    started_mutation = Event()
    original_audit = svc._audit

    def _observed_audit(db, biz_type, biz_id, audit_action, detail=""):
        if audit_action == action:
            started_mutation.set()
        return original_audit(db, biz_type, biz_id, audit_action, detail)

    monkeypatch.setattr(svc, "_audit", _observed_audit)
    blocker = _hold_tenant_lock(TID)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(invoke)
            # Deterministic RED: legacy writers mutate/audit without touching the
            # tenant coordination row, while the hardened writer must still wait.
            waited = not started_mutation.wait(timeout=0.35)
            blocker.commit()
            result = future.result(timeout=8)
        assert waited, "current-term writer bypassed the tenant Authority lock"
        return result
    finally:
        if blocker.in_transaction():
            blocker.rollback()
        blocker.close()


def test_set_current_term_serializes_on_tenant_authority_row(db_mode, monkeypatch):
    ids = _seed_terms()
    monkeypatch.setattr(svc, "_tid", lambda: TID)

    result = _assert_writer_waits_for_tenant_lock(
        monkeypatch,
        "SET_CURRENT",
        lambda: svc.set_current_term(ids["target"], {}),
    )
    assert int(result["termId"]) == ids["target"]
    assert result["isCurrent"] is True


def test_publish_term_uses_same_tenant_authority_row(db_mode, monkeypatch):
    ids = _seed_terms()
    monkeypatch.setattr(svc, "_tid", lambda: TID)

    result = _assert_writer_waits_for_tenant_lock(
        monkeypatch,
        "PUBLISH",
        lambda: svc.publish_term(ids["publish_target"], {}),
    )
    assert int(result["termId"]) == ids["publish_target"]
    assert result["status"] == "PUBLISHED"
    assert result["isCurrent"] is True


def test_two_current_term_writers_finish_with_one_current_and_keep_neighbor(db_mode, monkeypatch):
    ids = _seed_terms()
    monkeypatch.setattr(svc, "_tid", lambda: TID)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(svc.set_current_term, ids["target"], {})
        second = pool.submit(svc.publish_term, ids["publish_target"], {})
        first.result(timeout=10)
        second.result(timeout=10)

    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        own_current_count = db.scalar(
            select(func.count(AaTerm.id)).where(
                AaTerm.tenant_id == TID,
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            )
        )
        neighbor_current_ids = db.scalars(
            select(AaTerm.id).where(
                AaTerm.tenant_id == NEIGHBOR_TID,
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            )
        ).all()
        assert int(own_current_count or 0) == 1
        assert [int(value) for value in neighbor_current_ids] == [ids["neighbor"]]
    finally:
        db.close()
