"""A-W1 / A-C1: current-term Authority must be serialized per tenant on real MySQL.

These tests intentionally exercise the canonical writers instead of adding a second
term truth.  The deterministic RED holds the tenant coordination row before starting
a writer: a production-safe writer must wait for that row before it may mutate
``AaTerm.is_current``.  This proves all formal current-term writers share the same
tenant-scoped authority boundary, including calendar publish and legacy migration.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event

from sqlalchemy import func, select

from app.modules.academic_affairs.services import academic_affairs_service as svc

TID = 1000000000000000001
NEIGHBOR_TID = 1000000000000000099


def _seed_terms():
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTimeSlot, Tenant

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
            start_date=datetime(2092, 9, 1),
            end_date=datetime(2093, 1, 31),
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
        slot = AaTimeSlot(
            tenant_id=TID,
            slot_no=1,
            slot_name="A-W1 第一节",
            start_time="08:00",
            end_time="08:45",
            enabled=True,
            status="ENABLED",
        )
        db.add_all([current, target, publish_target, neighbor, slot])
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
            waited = not started_mutation.wait(timeout=0.35)
            blocker.commit()
            result = future.result(timeout=8)
        assert waited, "current-term writer bypassed the tenant Authority lock"
        return result
    finally:
        if blocker.in_transaction():
            blocker.rollback()
        blocker.close()


def _assert_future_waits_for_tenant_lock(invoke):
    blocker = _hold_tenant_lock(TID)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(invoke)
            waited = not future.done()
            if waited:
                # Give the worker a deterministic window to reach the current-term assignment.
                from time import sleep
                sleep(0.35)
                waited = not future.done()
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


def test_publish_calendar_uses_same_tenant_authority_row(db_mode, monkeypatch):
    ids = _seed_terms()
    monkeypatch.setattr(svc, "_tid", lambda: TID)

    result = _assert_writer_waits_for_tenant_lock(
        monkeypatch,
        "PUBLISH",
        lambda: svc.publish_calendar(
            ids["publish_target"],
            {"currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER"},
        ),
    )
    assert int(result["termId"]) == ids["publish_target"]
    assert result["status"] == "PUBLISHED"
    assert result["isCurrent"] is True


def test_legacy_term_import_current_flag_uses_same_authority_row(db_mode, monkeypatch):
    ids = _seed_terms()
    from app.db.session import get_sessionmaker
    from app.services import migration_import_service as migration

    monkeypatch.setattr(migration, "_tid", lambda: TID)

    def _invoke():
        db = get_sessionmaker()()
        try:
            result = migration._persist_term(
                db,
                [{
                    "yearCode": "2092-2093",
                    "termNo": 1,
                    "termName": "A-W1 历史导入当前学期",
                    "startDate": datetime(2092, 9, 1),
                    "endDate": datetime(2093, 1, 31),
                    "teachingWeeks": 17,
                    "examWeekStart": 16,
                    "isCurrent": True,
                }],
            )
            db.commit()
            return result
        finally:
            db.close()

    result = _assert_future_waits_for_tenant_lock(_invoke)
    assert result["updated"] == 1

    db = get_sessionmaker()()
    try:
        from app.models import AaTerm
        imported = db.get(AaTerm, ids["publish_target"])
        assert imported.is_current is True
    finally:
        db.close()


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
