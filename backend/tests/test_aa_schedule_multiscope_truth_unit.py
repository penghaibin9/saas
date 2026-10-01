from types import SimpleNamespace
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


TENANT_ID = 1000000000000000007


def _db():
    from app.models import (AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead,
                           AaTerm, StudentProfile, AaSelectionCourse, AaSelectionRecord,
                           AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion, AaTeachingClassTeacher)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    for model in (AaScheduleBatch, AaScheduleScopeHead, AaScheduleItem, AaTerm,
                  StudentProfile, AaSelectionCourse, AaSelectionRecord,
                  AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion, AaTeachingClassTeacher):
        model.__table__.create(engine)
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


def test_mobile_self_views_union_current_scopes_without_widening_membership(monkeypatch):
    from app.models import (AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead,
                           AaTerm, StudentProfile, AaSelectionCourse, AaSelectionRecord,
                           AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion, AaTeachingClassTeacher)
    from app.modules.academic_affairs.services import (
        academic_affairs_schedule_service as schedule,
        academic_affairs_schedule_facade as student_schedule,
        mobile_academic_affairs_facade as mobile,
    )

    with _db() as db:
        _seed(db)
        db.execute(AaTerm.__table__.insert().values(
            id=1, tenant_id=TENANT_ID, year_code="2026-2027", term_no=2,
            is_current=True, teaching_weeks=20))
        for batch_id, term_id, college_id in [(104, 1, 12), (105, 2, 12), (106, 1, 11)]:
            db.add(AaScheduleBatch(id=batch_id, tenant_id=TENANT_ID, term_id=term_id,
                                  college_id=college_id, batch_name=str(batch_id), status="PUBLISHED"))
        db.get(AaScheduleScopeHead, 203).active_batch_id = 104
        db.add(AaScheduleScopeHead(id=205, tenant_id=TENANT_ID, term_id=2,
                                  scope_type="COLLEGE", scope_id=12, active_batch_id=105))
        students = [StudentProfile(id=701, tenant_id=TENANT_ID, student_no="A", real_name="甲", class_id=21),
                    StudentProfile(id=702, tenant_id=TENANT_ID, student_no="B", real_name="乙", class_id=22)]
        db.add_all(students)
        for item_id in [301, 302, 303]:
            item = db.get(AaScheduleItem, item_id)
            item.class_id, item.teacher_key = 21, "teacher-a"
        for item_id, batch_id, task_id, class_id, teacher, status in [
            (304, 104, 504, 22, "teacher-b", "EFFECTIVE"),
            (305, 104, 508, 22, "teacher-a", "EFFECTIVE"),
            (306, 104, 507, 22, "teacher-a", "EFFECTIVE"),
            (307, 102, 506, 21, "teacher-b", "EFFECTIVE"),
            (308, 105, 508, 21, "teacher-a", "EFFECTIVE"),
            (309, 106, 509, 21, "teacher-a", "EFFECTIVE"),
            (310, 102, 510, 21, "teacher-a", "CANCELLED"),
            (311, 104, 511, 22, "teacher-b", "EFFECTIVE"),
        ]:
            db.add(AaScheduleItem(id=item_id, tenant_id=TENANT_ID, batch_id=batch_id,
                                 task_id=task_id, class_id=class_id, teacher_key=teacher,
                                 course_name=str(task_id), weekday=1, slot_no=1,
                                 start_week=1, end_week=18, week_parity="ALL", status=status))
        for class_id, task_id, member_id in [(801, 506, 702), (802, 507, 701)]:
            db.add(AaTeachingClass(id=class_id, tenant_id=TENANT_ID, teaching_task_id=task_id,
                                  term_id=1, course_id=task_id, class_code=str(class_id),
                                  class_name=str(class_id), current_roster_version_id=class_id,
                                  roster_status="LOCKED", status="ACTIVE"))
            db.add(AaTeachingClassRosterVersion(id=class_id, tenant_id=TENANT_ID,
                                               teaching_class_id=class_id, version_no=1,
                                               source_type="ADMIN_CLASS", roster_hash="test", status="LOCKED"))
            db.add(AaTeachingClassMember(id=class_id, tenant_id=TENANT_ID, teaching_class_id=class_id,
                                        roster_version_id=class_id, student_id=member_id,
                                        source_type="ADMIN_CLASS", status="ACTIVE"))
            db.add(AaTeachingClassTeacher(id=class_id, tenant_id=TENANT_ID, teaching_class_id=class_id,
                                         teacher_key="teacher-a" if class_id == 802 else "teacher-b",
                                         status="ACTIVE"))
        for course_id, task_id, status in [(901, 508, "LOCKED"), (902, 511, "SELECTED")]:
            db.add(AaSelectionCourse(id=course_id, tenant_id=TENANT_ID, batch_id=900,
                                    course_id=task_id, teaching_task_id=task_id))
            db.add(AaSelectionRecord(id=course_id, tenant_id=TENANT_ID, batch_id=900,
                                    selection_course_id=course_id, student_id=701, status=status))
        db.commit()

        @contextmanager
        def session():
            yield db

        monkeypatch.setattr(mobile._legacy, "session", session)
        monkeypatch.setattr(student_schedule._legacy, "session", session)
        monkeypatch.setattr(mobile._legacy, "_me", lambda db, user: db.get(StudentProfile, user["studentId"]))
        monkeypatch.setattr(mobile, "_schedule_meta", lambda db, term, batch: {"teachingWeeks": 20, "currentWeek": 1})
        monkeypatch.setattr(mobile, "_student_today_context", lambda db, term: {"todayWeek": 1})
        checked_permissions = []
        monkeypatch.setattr(mobile, "enforce_permission", lambda user, permission: checked_permissions.append(permission))

        for student_id, expected in [(701, {"301", "302", "305", "306"}), (702, {"304", "305", "307", "311"})]:
            result = mobile.schedule_my({"studentId": student_id}, week=1)
            assert {item["itemId"] for item in result["items"]} == expected
            assert result["batchId"] is None
            assert result["batchIds"] == ["101", "102", "104"]
        for teacher, expected in [("teacher-a", {"301", "302", "305", "306"}),
                                  ("teacher-b", {"304", "307", "311"})]:
            result = mobile.teacher_schedule_my({"userType": "TEACHER", "loginName": teacher}, week=1)
            assert {item["itemId"] for item in result["items"]} == expected
            assert result["batchIds"] == ["101", "102", "104"]
        assert checked_permissions == ["academicAffairs.schedule.view"] * 2
        scalar = schedule.student_view(104, {}, 701)
        assert {item["itemId"] for item in scalar["items"]} == {"305", "306"}
        assert next(item for item in scalar["items"] if item["itemId"] == "305")["source"] == "ENROLLED"
