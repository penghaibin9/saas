from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


TENANT_ID = 1000000000000000007


def _db():
    from app.models import AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead

    engine = create_engine("sqlite+pysqlite:///:memory:")
    AaScheduleBatch.__table__.create(engine)
    AaScheduleScopeHead.__table__.create(engine)
    AaScheduleItem.__table__.create(engine)
    return Session(engine)


def _seed(db):
    from app.core.context import set_tenant
    from app.models import AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead

    set_tenant({"tenantId": str(TENANT_ID)})
    batches = [
        AaScheduleBatch(
            id=101, tenant_id=TENANT_ID, term_id=1, batch_name="全校正式课表",
            college_id=None, status="PUBLISHED",
        ),
        AaScheduleBatch(
            id=102, tenant_id=TENANT_ID, term_id=1, batch_name="信息学院正式课表",
            college_id=11, status="PUBLISHED",
        ),
        AaScheduleBatch(
            id=103, tenant_id=TENANT_ID, term_id=1, batch_name="已顶替课表",
            college_id=12, status="SUPERSEDED",
        ),
    ]
    db.add_all(batches)
    db.add_all([
        AaScheduleScopeHead(
            id=201, tenant_id=TENANT_ID, term_id=1, scope_type="SCHOOL",
            scope_id=0, active_batch_id=101,
        ),
        AaScheduleScopeHead(
            id=202, tenant_id=TENANT_ID, term_id=1, scope_type="COLLEGE",
            scope_id=11, active_batch_id=102,
        ),
        # A corrupt/stale head must not resurrect a historical batch.
        AaScheduleScopeHead(
            id=203, tenant_id=TENANT_ID, term_id=1, scope_type="COLLEGE",
            scope_id=12, active_batch_id=103,
        ),
    ])
    db.add_all([
        AaScheduleItem(
            id=301, tenant_id=TENANT_ID, batch_id=101, task_id=501,
            course_name="大学语文", weekday=1, slot_no=1,
            start_week=1, end_week=18, week_parity="ALL",
            classroom_text="A101", status="EFFECTIVE", source="MANUAL",
        ),
        AaScheduleItem(
            id=302, tenant_id=TENANT_ID, batch_id=102, task_id=502,
            course_name="软件测试", weekday=2, slot_no=2,
            start_week=1, end_week=18, week_parity="ALL",
            classroom_text="B202", status="EFFECTIVE", source="MANUAL",
        ),
        AaScheduleItem(
            id=303, tenant_id=TENANT_ID, batch_id=103, task_id=503,
            course_name="历史旧课", weekday=3, slot_no=3,
            start_week=1, end_week=18, week_parity="ALL",
            classroom_text="C303", status="EFFECTIVE", source="MANUAL",
        ),
    ])
    db.commit()


def test_scopehead_union_keeps_school_and_college_batches_only():
    from app.modules.academic_affairs.services import (
        academic_affairs_schedule_service as schedule_service,
        academic_affairs_schedule_truth_service as truth_service,
    )

    with _db() as db:
        _seed(db)

        assert truth_service.active_batch_ids(db, [1]) == [101, 102]
        batches = schedule_service._current_published_batches(db, 1)
        assert [int(batch.id) for batch in batches] == [101, 102]
        assert schedule_service._batch_identity(batches) == {
            "batchId": None,
            "batchIds": ["101", "102"],
        }


def test_selection_projection_reads_each_active_scope_batch():
    from app.modules.academic_affairs.services import (
        academic_affairs_selection_final_service as selection_service,
    )

    with _db() as db:
        _seed(db)
        projection = selection_service._student_course_schedule_projection(
            db,
            [SimpleNamespace(term_id=1)],
            [
                SimpleNamespace(teaching_task_id=501),
                SimpleNamespace(teaching_task_id=502),
                SimpleNamespace(teaching_task_id=503),
            ],
        )

        assert set(projection) == {501, 502}
        assert projection[501][0]["scheduleItemId"] == "301"
        assert projection[502][0]["scheduleItemId"] == "302"
