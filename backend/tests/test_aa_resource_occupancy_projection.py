"""SR020 resource occupancy projection using the real service and isolated SQLite.

No external database or db_mode fixture. Installed term authority guards stay active.
Calendar completeness and approval commands are outside this read projection contract.
"""
from contextlib import contextmanager
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


TID = 1000000000000000007
DAY = "2026-09-15"  # Existing resource mapping: week 3, Tuesday.


@pytest.fixture
def occupancy_db(monkeypatch):
    from app.core.context import set_tenant
    from app.models import Tenant, AaTerm, AaCalendarEvent, AaScheduleBatch, AaScheduleScopeHead, AaScheduleItem, AaClassroomBooking, AaLabBooking, AaLabResource
    from app.models.academic_calendar import AcademicCalendarGovernance, ACTIVE_SENTINEL, CALENDAR_STATUS_ACTIVE

    from app.modules.academic_affairs.services import academic_affairs_resource_service as resource_service
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for model in (Tenant, AcademicCalendarGovernance, AaTerm, AaCalendarEvent, AaScheduleBatch, AaScheduleScopeHead, AaScheduleItem, AaClassroomBooking, AaLabResource, AaLabBooking):
        model.__table__.create(engine)
    set_tenant({"tenantId": str(TID)})
    with Session(engine) as db:
        # Persist the real tenant anchors before any current-term/ACTIVE writer.
        db.add_all([Tenant(id=TID, tenant_code="SR020", school_name="SR020 isolated fixture"),
                    Tenant(id=TID + 1, tenant_code="SR020-OTHER", school_name="Other isolated tenant")])
        db.flush()
        term = AaTerm(id=1, tenant_id=TID, year_code="2026-2027", term_no=1,
                      start_date=datetime(2026, 9, 1), end_date=datetime(2027, 1, 4),
                      teaching_weeks=18, status="PUBLISHED", is_current=False)
        governance = AcademicCalendarGovernance(id=901, tenant_id=TID, term_id=1)
        db.add_all([term, governance])
        db.flush()
        # Keep the installed ORM listeners: ACTIVE and current align through the
        # actual Tenant lock/authority queries, with no guard patched or bypassed.
        governance.governance_status = CALENDAR_STATUS_ACTIVE
        governance.active_key = ACTIVE_SENTINEL
        db.flush()
        term.is_current = True
        db.flush()
        # Current SCHOOL + COLLEGE; history, other term, unheaded published and foreign tenant.
        for bid, term, college, status, tenant in [(101, 1, None, "PUBLISHED", TID), (102, 1, 11, "PUBLISHED", TID), (103, 1, 12, "SUPERSEDED", TID), (104, 2, None, "PUBLISHED", TID), (105, 1, 13, "PUBLISHED", TID), (106, 1, 14, "PUBLISHED", TID + 1)]:
            db.add(AaScheduleBatch(id=bid, tenant_id=tenant, term_id=term, college_id=college, batch_name=f"batch-{bid}", status=status))
            db.add(AaScheduleItem(id=bid + 200, tenant_id=tenant, batch_id=bid, classroom_id=bid + 600,
                                  classroom_text="同名资源", course_name=f"course-{bid}", weekday=2, slot_no=5,
                                  start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE"))
        for hid, bid, term, scope, scope_id, tenant in [(201, 101, 1, "SCHOOL", 0, TID), (202, 102, 1, "COLLEGE", 11, TID), (204, 104, 2, "SCHOOL", 0, TID), (206, 106, 1, "COLLEGE", 14, TID + 1)]:
            db.add(AaScheduleScopeHead(id=hid, tenant_id=tenant, term_id=term, scope_type=scope, scope_id=scope_id, active_batch_id=bid))
        db.commit()

        @contextmanager
        def read_session():
            yield db

        monkeypatch.setattr(resource_service, "session", read_session)
        yield resource_service, db
    engine.dispose()


def test_current_scope_union_and_exact_resource_identity(occupancy_db):
    resource_service, _ = occupancy_db
    result = resource_service.get_resource_occupancy(None, DAY, "CLASSROOM")
    assert {(row["resourceId"], row["purpose"]) for row in result["items"]} == {("701", "course-101"), ("702", "course-102")}
    assert result["total"] == 2


def test_missing_id_remains_unknown_not_matched_by_label(occupancy_db):
    from app.models import AaScheduleItem
    resource_service, db = occupancy_db
    db.get(AaScheduleItem, 301).classroom_id = None
    db.flush()
    rows = resource_service.get_resource_occupancy(None, DAY)["items"]
    assert {row["purpose"]: row["resourceId"] for row in rows} == {"course-101": "", "course-102": "702"}


def test_lab_does_not_consume_classroom_schedule_even_with_same_id_or_name(occupancy_db):
    from app.models import AaLabBooking
    resource_service, db = occupancy_db
    db.add(AaLabBooking(id=401, tenant_id=TID, lab_id=701, lab_text="同名资源", booking_date=DAY,
                        slot_no=5, status="APPROVED", applicant_name="资源管理员"))
    db.commit()
    result = resource_service.get_resource_occupancy(None, DAY, "LAB")
    assert result["total"] == 1
    assert {(row["resourceKind"], row["source"], row["resourceId"]) for row in result["items"]} == {("LAB", "BOOKING", "701")}


def test_no_head_does_not_fall_back_to_effective_rows(occupancy_db):
    from app.models import AaScheduleScopeHead
    resource_service, db = occupancy_db
    for row in db.query(AaScheduleScopeHead).all():
        row.is_deleted = True
    db.flush()
    assert resource_service.get_resource_occupancy(None, DAY)["items"] == []


def test_existing_week_mapping_parity_and_out_of_range_are_preserved(occupancy_db):
    from app.models import AaScheduleItem
    resource_service, db = occupancy_db
    db.get(AaScheduleItem, 301).week_parity = "EVEN"
    db.flush()
    assert [row["purpose"] for row in resource_service.get_resource_occupancy(None, DAY)["items"]] == ["course-102"]
    assert resource_service.get_resource_occupancy(None, "2026-08-31")["items"] == []
    assert resource_service.get_resource_occupancy(None, "2027-03-01")["items"] == []
    from app.core.exceptions import AppException
    with pytest.raises(AppException, match="日期格式"):
        resource_service.get_resource_occupancy(None, "bad-date", "LAB")


def test_legacy_helper_keeps_call_shape_but_returns_only_formal_rows(occupancy_db):
    resource_service, db = occupancy_db
    legacy_ids = {row.id for row in resource_service._schedule_items_on_date(db, DAY)}
    formal_ids = {row.id for row in resource_service._schedule_items_on_date(db, DAY, active_only=True)}
    assert legacy_ids == {301, 302}
    assert formal_ids == {301, 302}
