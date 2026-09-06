"""P1-01 / AA-001: term command Authority and legacy current serialization."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_dashboard_scope_facade as facade

TID = 1000000000000000801

TENANT_USER = {
    "userId": "aa-r3-academic-admin",
    "loginName": "aa-r3-academic-admin",
    "userType": "TEACHER",
    "currentRoleCode": "ACADEMIC_ADMIN",
}
COLLEGE_USER = {
    "userId": "aa-r3-college-admin",
    "loginName": "aa-r3-college-admin",
    "userType": "TEACHER",
    "currentRoleCode": "COLLEGE_ADMIN",
}


def _patch_tenant(monkeypatch) -> None:
    from app.core import affairs_security
    from app.modules.academic_affairs.services import academic_affairs_archive_core_service as archive_core

    monkeypatch.setattr(facade._legacy, "_tid", lambda: TID)
    monkeypatch.setattr(affairs_security, "_tid", lambda: TID)
    monkeypatch.setattr(archive_core, "_tid", lambda: TID)


def _seed_terms():
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-term-authority",
                school_name="AA R3 学期 Authority 学校",
                short_name="AA R3 学期学校",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        current = AaTerm(
            tenant_id=TID,
            year_code="2093-2094",
            term_no=1,
            term_name="R3 当前学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        switch_a = AaTerm(
            tenant_id=TID,
            year_code="2093-2094",
            term_no=2,
            term_name="R3 切换学期 A",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        switch_b = AaTerm(
            tenant_id=TID,
            year_code="2094-2095",
            term_no=1,
            term_name="R3 切换学期 B",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        draft = AaTerm(
            tenant_id=TID,
            year_code="2094-2095",
            term_no=2,
            term_name="R3 待发布定义",
            teaching_weeks=18,
            status="DRAFT",
            is_current=False,
        )
        db.add_all([current, switch_a, switch_b, draft])
        db.commit()
        return {
            "current": int(current.id),
            "switch_a": int(switch_a.id),
            "switch_b": int(switch_b.id),
            "draft": int(draft.id),
        }
    finally:
        db.close()


def _activate_governance(term_id: int) -> None:
    from app.db.session import get_sessionmaker
    from app.models.academic_calendar import (
        ACTIVE_SENTINEL,
        CALENDAR_STATUS_ACTIVE,
        CALENDAR_TYPE_ACADEMIC,
        AcademicCalendarGovernance,
    )

    db = get_sessionmaker()()
    try:
        db.add(AcademicCalendarGovernance(
            tenant_id=TID,
            term_id=int(term_id),
            calendar_type=CALENDAR_TYPE_ACADEMIC,
            timezone="Asia/Shanghai",
            governance_status=CALENDAR_STATUS_ACTIVE,
            active_key=ACTIVE_SENTINEL,
        ))
        db.commit()
    finally:
        db.close()


def _term_facts(ids):
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        rows = db.scalars(
            select(AaTerm).where(AaTerm.id.in_(list(ids))).order_by(AaTerm.id)
        ).all()
        return {
            int(row.id): (row.status, bool(row.is_current))
            for row in rows
        }
    finally:
        db.close()


def test_governance_publish_only_publishes_definition_without_changing_current_flag(db_mode, monkeypatch):
    ids = _seed_terms()
    _patch_tenant(monkeypatch)
    _activate_governance(ids["current"])
    before = _term_facts(ids.values())

    row = facade.publish_term(ids["draft"], TENANT_USER)

    after = _term_facts(ids.values())
    assert row["status"] == "PUBLISHED"
    assert row["isCurrent"] is False
    assert after[ids["draft"]] == ("PUBLISHED", False)
    for key in ("current", "switch_a", "switch_b"):
        assert after[ids[key]][1] == before[ids[key]][1]


def test_governance_set_current_is_rejected_with_switch_route(db_mode, monkeypatch):
    ids = _seed_terms()
    _patch_tenant(monkeypatch)
    _activate_governance(ids["current"])
    before = _term_facts(ids.values())

    with pytest.raises(AppException) as exc:
        facade.set_current_term(ids["switch_a"], TENANT_USER)

    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    assert exc.value.details["switchRoute"] == "/admin/system/academic-calendar"
    assert _term_facts(ids.values()) == before


def test_college_scope_cannot_publish_or_switch_term_even_with_permission_code(db_mode, monkeypatch):
    ids = _seed_terms()
    _patch_tenant(monkeypatch)
    before = _term_facts(ids.values())

    with pytest.raises(AppException) as publish_exc:
        facade.publish_term(ids["draft"], COLLEGE_USER)
    with pytest.raises(AppException) as switch_exc:
        facade.set_current_term(ids["switch_a"], COLLEGE_USER)

    assert publish_exc.value.code == "NO_DATA_SCOPE"
    assert switch_exc.value.code == "NO_DATA_SCOPE"
    assert _term_facts(ids.values()) == before


def test_legacy_two_concurrent_switches_leave_exactly_one_current(db_mode, monkeypatch):
    ids = _seed_terms()
    _patch_tenant(monkeypatch)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(facade.set_current_term, ids["switch_a"], TENANT_USER)
        second = pool.submit(facade.set_current_term, ids["switch_b"], TENANT_USER)
        first.result(timeout=10)
        second.result(timeout=10)

    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    db = get_sessionmaker()()
    try:
        current_ids = db.scalars(
            select(AaTerm.id).where(
                AaTerm.tenant_id == TID,
                AaTerm.is_deleted.is_(False),
                AaTerm.is_current.is_(True),
            )
        ).all()
        current_count = db.scalar(
            select(func.count(AaTerm.id)).where(
                AaTerm.tenant_id == TID,
                AaTerm.is_deleted.is_(False),
                AaTerm.is_current.is_(True),
            )
        )
        assert int(current_count or 0) == 1
        assert [int(value) for value in current_ids][0] in {ids["switch_a"], ids["switch_b"]}
    finally:
        db.close()
