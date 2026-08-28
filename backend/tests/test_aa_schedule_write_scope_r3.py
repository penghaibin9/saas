"""P1-05 / AA-008 targeted MySQL regression for schedule batch write Authority."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as svc
from app.modules.academic_affairs.services import academic_affairs_schedule_write_scope_r3 as guard

TID = 1000000000000000808
COLLEGE_USER = {
    "userId": "aa-r3-schedule-college-a",
    "loginName": "aa-r3-schedule-college-a",
    "userType": "TEACHER",
    "currentRoleCode": "COLLEGE_ADMIN",
}
SCHOOL_USER = {
    "userId": "aa-r3-schedule-school",
    "loginName": "aa-r3-schedule-school",
    "userType": "TEACHER",
    "currentRoleCode": "ACADEMIC_ADMIN",
}


def _patch(monkeypatch):
    from app.core import affairs_security
    from app.models import AaTerm

    monkeypatch.setattr(svc._base, "_tid", lambda: TID)
    monkeypatch.setattr(affairs_security, "_tid", lambda: TID)

    def fake_scope(db, term_id=None, batch_id=None, writable=True):
        term = db.get(AaTerm, int(term_id))
        if not term:
            raise AppException("DATA_CONFLICT", "测试学期不存在")
        return term, None, int(term.teaching_weeks or 18)

    monkeypatch.setattr(svc.policy, "resolve_scope", fake_scope)


def _seed():
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem, AaTerm, College, TeacherStudentScope, Tenant

    db = get_sessionmaker()()
    try:
        if db.get(Tenant, TID) is None:
            db.add(Tenant(
                id=TID,
                tenant_code="aa-r3-schedule-scope",
                school_name="AA R3 排课 Scope 学校",
                short_name="AA R3 排课",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        college_a = College(tenant_id=TID, college_name="R3 排课学院 A", code="R3SA", status="ACTIVE")
        college_b = College(tenant_id=TID, college_name="R3 排课学院 B", code="R3SB", status="ACTIVE")
        db.add_all([college_a, college_b])
        db.flush()
        term = AaTerm(
            tenant_id=TID,
            year_code="2098-2099",
            term_no=1,
            term_name="R3 排课权限学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        db.add(term)
        db.flush()
        own = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="R3 本院课表", college_id=college_a.id, status="DRAFT")
        other = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="R3 外院课表", college_id=college_b.id, status="DRAFT")
        school = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="R3 全校课表", college_id=None, status="DRAFT")
        db.add_all([own, other, school])
        db.flush()
        other_item = AaScheduleItem(
            tenant_id=TID,
            batch_id=other.id,
            weekday=2,
            slot_no=2,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            status="EFFECTIVE",
            source="MANUAL",
        )
        db.add(other_item)
        db.add(TeacherStudentScope(
            tenant_id=TID,
            teacher_key=COLLEGE_USER["loginName"],
            teacher_name="R3 排课学院 A 教务",
            role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE",
            ref_value=college_a.college_name,
            status="ACTIVE",
        ))
        db.commit()
        return {
            "term": int(term.id),
            "college_a": int(college_a.id),
            "college_b": int(college_b.id),
            "own": int(own.id),
            "other": int(other.id),
            "school": int(school.id),
            "other_item": int(other_item.id),
        }
    finally:
        db.close()


def _counts(ids):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem, AaSchedulePublish

    db = get_sessionmaker()()
    try:
        return {
            "other_status": db.get(AaScheduleBatch, ids["other"]).status,
            "other_items": db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == ids["other"]).count(),
            "publish": db.query(AaSchedulePublish).filter(AaSchedulePublish.batch_id == ids["other"]).count(),
        }
    finally:
        db.close()


def _stub_add(monkeypatch):
    from app.models import AaScheduleItem

    monkeypatch.setattr(svc, "_resolve_task", lambda *_a, **_k: SimpleNamespace(id=88001))

    def fake_build(_db, batch, _task, _source, *, item_source, preload=None):
        return AaScheduleItem(
            tenant_id=TID,
            batch_id=batch.id,
            weekday=1,
            slot_no=1,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            status="EFFECTIVE",
            source=item_source,
        )

    monkeypatch.setattr(svc, "_build_item", fake_build)


def test_college_can_create_and_write_own_batch(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch); _stub_add(monkeypatch)
    body = SimpleNamespace(termId=ids["term"], batchName="R3 学院新批次", collegeId=ids["college_a"])
    created = svc.create_batch(body, COLLEGE_USER)
    row = svc.add_item(int(created["batchId"]), COLLEGE_USER, SimpleNamespace())
    assert created["status"] == "DRAFT"
    assert row["batchId"] == created["batchId"]


def test_college_cannot_create_other_college_or_schoolwide_batch(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch)
    for college_id in (ids["college_b"], None):
        body = SimpleNamespace(termId=ids["term"], batchName=f"R3 deny {college_id}", collegeId=college_id)
        with pytest.raises(AppException) as exc:
            svc.create_batch(body, COLLEGE_USER)
        assert exc.value.code == "NO_DATA_SCOPE"


def test_college_cannot_add_import_move_pre_publish_publish_other_college_batch(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch)
    calls = [
        lambda: svc.add_item(ids["other"], COLLEGE_USER, SimpleNamespace()),
        lambda: svc.import_items(ids["other"], COLLEGE_USER, [], atomic=True),
        lambda: svc.move_item(ids["other_item"], COLLEGE_USER, SimpleNamespace(weekday=3, slotNo=3)),
        lambda: svc.adjust_item(ids["other"], ids["other_item"], COLLEGE_USER, 3, 3, None),
        lambda: svc.pre_publish(ids["other"], COLLEGE_USER),
        lambda: svc.publish(ids["other"], COLLEGE_USER),
    ]
    for call in calls:
        with pytest.raises(AppException) as exc:
            call()
        assert exc.value.code == "NO_DATA_SCOPE"


def test_denied_writes_leave_items_status_publish_facts_unchanged(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch)
    before = _counts(ids)
    for call in (
        lambda: svc.import_items(ids["other"], COLLEGE_USER, [{"weekday": 1}], atomic=False),
        lambda: svc.move_item(ids["other_item"], COLLEGE_USER, SimpleNamespace(weekday=4, slotNo=4)),
        lambda: svc.publish(ids["other"], COLLEGE_USER),
    ):
        with pytest.raises(AppException):
            call()
    assert _counts(ids) == before


def test_tenant_all_keeps_schoolwide_and_cross_college_admin_capability(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch)
    for college_id in (None, ids["college_b"]):
        body = SimpleNamespace(termId=ids["term"], batchName=f"R3 school {college_id}", collegeId=college_id)
        row = svc.create_batch(body, SCHOOL_USER)
        assert row["status"] == "DRAFT"


def test_own_college_publish_still_must_pass_existing_integrity_gate(db_mode, monkeypatch):
    ids = _seed(); _patch(monkeypatch)

    def blocked(*_args, **_kwargs):
        raise AppException("SCHEDULE_INTEGRITY_BLOCKED", "existing gate still authoritative", http_status=409)

    monkeypatch.setattr(svc.gate_service, "require_publishable", blocked)
    with pytest.raises(AppException) as exc:
        svc.pre_publish(ids["own"], COLLEGE_USER)
    assert exc.value.code == "SCHEDULE_INTEGRITY_BLOCKED"
