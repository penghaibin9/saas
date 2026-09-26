"""开课责任动态范围：规则检查与由主控串行执行的真实 MySQL 回归。"""
from types import SimpleNamespace as Row
from unittest.mock import MagicMock
import importlib
from contextlib import contextmanager

import pytest
from app.core.exceptions import AppException

service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_service")


def test_exam_scope_uses_live_owner_and_rejects_unresolved_even_for_school(monkeypatch):
    monkeypatch.setattr(service, "_course_college_id", lambda db, course: 12)
    ctx = Row(scope_type="COLLEGE", college_ids={12})
    assert service._check_course_scope(MagicMock(), ctx, Row(id=9, college_id=34)) == 12
    with pytest.raises(Exception):
        service._check_course_scope(MagicMock(), Row(scope_type="COLLEGE", college_ids={34}), Row(id=9, college_id=34))
    monkeypatch.setattr(service, "_course_college_id", lambda db, course: None)
    with pytest.raises(Exception, match="开课责任"):
        service._check_course_scope(MagicMock(), Row(scope_type="TENANT_ALL"), Row(id=9))


def test_public_exam_confirmation_denies_stale_college_before_mutation(monkeypatch):
    facade = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_facade")
    db, audit = MagicMock(), MagicMock()
    course = Row(id=9, college_id=34, status="PENDING_CONFIRM")
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_ctx", lambda user, db: Row(scope_type="COLLEGE", college_ids={34}))
    monkeypatch.setattr(service, "_get_course", lambda db, cid: course)
    monkeypatch.setattr(service, "_course_college_id", lambda db, course: 12)
    monkeypatch.setattr(service, "_audit", audit)
    with pytest.raises(Exception, match="学院范围"):
        facade.confirm_course({}, 9, "CONFIRM")
    assert course.status == "PENDING_CONFIRM"
    db.commit.assert_not_called()
    audit.assert_not_called()


def test_exam_room_and_invigilator_reads_reject_foreign_offering_college(monkeypatch):
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "_ctx", lambda user, db: Row(scope_type="COLLEGE", college_ids={34}))
    monkeypatch.setattr(service, "_get_course", lambda db, cid: Row(id=9))
    monkeypatch.setattr(service, "_course_college_id", lambda db, course: 12)
    db.query.return_value.filter.return_value.first.return_value = Row(exam_course_id=9)
    for reader in (service.list_rooms, service.list_invigilators, service.room_seats):
        with pytest.raises(Exception, match="学院范围"):
            reader({}, 9)


def test_exam_handoffs_use_current_stage_permission_and_cache(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    school = MagicMock(side_effect=lambda db, permission_code: {"permission": permission_code})
    monkeypatch.setattr(resolver, "resolve_school", school)
    batches = [Row(id=1, status="COURSE_CONFIRMED"), Row(id=2, status="ARRANGED"),
               Row(id=3, status="ARRANGED"), Row(id=4, status="ARCHIVED")]
    result = service._batch_handoffs(MagicMock(), batches, Row(scope_type="TENANT_ALL"))
    assert result[1]["responsibility"]["permission"] == "academicAffairs.exam.arrange"
    assert result[2]["responsibility"]["permission"] == "academicAffairs.exam.publish"
    assert result[4] == {"responsibility": None, "nextStep": None}
    assert school.call_count == 2


@pytest.mark.parametrize("scope,permission,resolved,actor", [
    ("TENANT_ALL", True, True, "17"),
    ("COLLEGE", False, True, "17"),
    ("COLLEGE", True, False, "17"),
    ("COLLEGE", True, True, "99"),
])
def test_public_confirmation_requires_current_college_actor_before_writes(monkeypatch, scope, permission, resolved, actor):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    facade = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_facade")
    db = MagicMock()
    course = Row(id=9, status="PENDING_CONFIRM")
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_ctx", lambda *args: Row(scope_type=scope, college_ids={12},
        permission_codes={"academicAffairs.exam.manage"} if permission else set()))
    monkeypatch.setattr(service, "_get_course", lambda *args: course)
    monkeypatch.setattr(service, "_course_college_id", lambda *args: 12)
    monkeypatch.setattr(resolver, "resolve_organization", lambda *args, **kw: {
        "resolved": resolved, "assigneeUserIds": [actor], "reason": "任职已失效"})
    monkeypatch.setattr(identity, "_current_user_id", lambda db, user: 17)
    with pytest.raises(AppException) as denied:
        facade.confirm_course({"userId": "17"}, 9, "CONFIRM")
    assert denied.value.code == "NO_DATA_SCOPE"
    assert course.status == "PENDING_CONFIRM"
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_course_confirmer_uses_exact_offering_college_and_current_permission(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    owner = {"resolved": True, "assigneeUserIds": ["17"]}
    resolve = MagicMock(return_value=owner)
    monkeypatch.setattr(resolver, "resolve_organization", resolve)
    monkeypatch.setattr(identity, "_current_user_id", lambda db, user: 17)
    monkeypatch.setattr(service, "_course_college_id", lambda *args: 12)
    db = MagicMock()
    ctx = Row(scope_type="COLLEGE", college_ids={12}, permission_codes={"academicAffairs.exam.manage"})
    assert service._require_course_confirmer(db, {"userId": "17"}, ctx, Row(id=9)) is owner
    resolve.assert_called_once_with(db, "COLLEGE", 12, permission_code="academicAffairs.exam.manage")


@pytest.mark.parametrize("scope,permission,resolved,actor", [
    ("COLLEGE", True, True, "17"),
    ("TENANT_ALL", False, True, "17"),
    ("TENANT_ALL", True, False, "17"),
    ("TENANT_ALL", True, True, "99"),
])
def test_public_publish_denies_invalid_school_actor_before_arrangement(monkeypatch, scope, permission, resolved, actor):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    facade = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_facade")
    db, arrangement = MagicMock(), MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_ctx", lambda *args: Row(scope_type=scope,
        permission_codes={"academicAffairs.exam.publish"} if permission else set()))
    monkeypatch.setattr(resolver, "resolve_school", lambda *args, **kw: {
        "resolved": resolved, "assigneeUserIds": [actor], "reason": "任职已失效"})
    monkeypatch.setattr(identity, "_current_user_id", lambda db, user: 17)
    monkeypatch.setattr(facade, "_check_arrangement_complete", arrangement)
    with pytest.raises(AppException) as denied:
        facade.publish_batch({"userId": "17"}, 9)
    assert denied.value.code == "NO_DATA_SCOPE"
    arrangement.assert_not_called()
    db.commit.assert_not_called()


def test_school_publisher_rechecks_active_stable_account(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    owner = {"resolved": True, "assigneeUserIds": ["17"]}
    resolve = MagicMock(return_value=owner)
    monkeypatch.setattr(resolver, "resolve_school", resolve)
    monkeypatch.setattr(identity, "_current_user_id", lambda db, user: 17)
    db = MagicMock()
    ctx = Row(scope_type="TENANT_ALL", permission_codes={"academicAffairs.exam.publish"})
    assert service._require_school_publisher(db, {"userId": "17"}, ctx) is owner
    resolve.assert_called_once_with(db, permission_code="academicAffairs.exam.publish")
    monkeypatch.setattr(identity, "_current_user_id", MagicMock(side_effect=AppException("NO_PERMISSION", "账号已停用")))
    with pytest.raises(Exception, match="账号已失效"):
        service._require_school_publisher(db, {"userId": "17"}, ctx)


def test_course_action_page_reuses_current_actor_and_college_decision(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    monkeypatch.setattr(resolver, "_tid", lambda: 1)
    owner = MagicMock(return_value={"resolved": True, "assigneeUserIds": ["17"]})
    account = MagicMock(return_value=17)
    monkeypatch.setattr(resolver, "resolve_organization", owner)
    monkeypatch.setattr(identity, "_current_user_id", account)
    rows = [(Row(id=index, status="PENDING_CONFIRM"), 12) for index in range(1, 101)]
    rows += [(Row(id=101, status="PENDING_CONFIRM"), 34), (Row(id=102, status="CONFIRMED"), 12),
             (Row(id=103, status="UNKNOWN"), 12), (Row(id=104, status="PENDING_CONFIRM"), None)]
    ctx = Row(scope_type="COLLEGE", college_ids={12, 34}, permission_codes={"academicAffairs.exam.manage"})
    actions = service._course_confirm_actions(MagicMock(), {"userId": "17"}, ctx, rows)
    assert all(actions[index] == {"allowed": True, "reason": ""} for index in range(1, 102))
    assert all(not actions[index]["allowed"] and actions[index]["reason"] for index in (102, 103, 104))
    assert owner.call_count == 2
    assert account.call_count == 1
    assert owner.call_args_list[0].kwargs["cache"] is owner.call_args_list[1].kwargs["cache"]
    # 第二个请求重新查权，上一页的允许结果不能跨请求复用。
    owner.return_value = {"resolved": False, "reason": "岗位任职已失效"}
    refreshed = service._course_confirm_actions(MagicMock(), {"userId": "17"}, ctx, rows[:1])
    assert not refreshed[1]["allowed"] and refreshed[1]["reason"] == "岗位任职已失效"
    assert owner.call_count == 3


@pytest.mark.parametrize("scope,permission,owner", [
    ("TENANT_ALL", True, {"resolved": True, "assigneeUserIds": ["17"]}),
    ("COLLEGE", False, {"resolved": True, "assigneeUserIds": ["17"]}),
    ("COLLEGE", True, {"resolved": False, "reason": "任职已失效"}),
    ("COLLEGE", True, {"resolved": True, "assigneeUserIds": ["99"]}),
    ("COLLEGE", True, {"resolved": True}),
    ("COLLEGE", True, {}),
])
def test_confirmation_action_is_false_for_school_revocation_or_unknown_fields(monkeypatch, scope, permission, owner):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    monkeypatch.setattr(resolver, "_tid", lambda: 1)
    monkeypatch.setattr(resolver, "resolve_organization", lambda *args, **kw: owner)
    monkeypatch.setattr(identity, "_current_user_id", lambda *args: 17)
    ctx = Row(scope_type=scope, college_ids={12}, permission_codes={"academicAffairs.exam.manage"} if permission else set())
    action = service._course_confirm_actions(MagicMock(), {"userId": "17"}, ctx,
        [(Row(id=9, status="PENDING_CONFIRM"), 12)])[9]
    assert action["allowed"] is False and action["reason"]


def test_publish_action_uses_live_command_guard_without_rechecking_each_batch(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as resolver
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    monkeypatch.setattr(resolver, "_tid", lambda: 1)
    owner = MagicMock(return_value={"resolved": True, "assigneeUserIds": ["17"]})
    account = MagicMock(return_value=17)
    monkeypatch.setattr(resolver, "resolve_school", owner)
    monkeypatch.setattr(identity, "_current_user_id", account)
    ctx = Row(scope_type="TENANT_ALL", permission_codes={"academicAffairs.exam.publish"})
    db, cache = MagicMock(), {}
    for status in ("COURSE_CONFIRMED", "ARRANGED"):
        assert service._batch_publish_action(db, {"userId": "17"}, ctx, Row(status=status), cache=cache)["allowed"] is True
    assert owner.call_count == account.call_count == 1
    for status in ("DRAFT", "PUBLISHED", "FINISHED", "ARCHIVED", "UNKNOWN", None):
        action = service._batch_publish_action(db, {"userId": "17"}, ctx, Row(status=status), cache=cache)
        assert action["allowed"] is False and action["reason"]
    owner.return_value = {"resolved": False, "reason": "学校责任人任职已失效"}
    action = service._batch_publish_action(db, {"userId": "17"}, ctx, Row(status="ARRANGED"), cache={})
    assert action == {"allowed": False, "reason": "学校责任人任职已失效"}
    college = Row(scope_type="COLLEGE", permission_codes={"academicAffairs.exam.publish"})
    assert not service._batch_publish_action(db, {"userId": "17"}, college, Row(status="ARRANGED"), cache={})["allowed"]


def test_mysql_exam_college_confirmation_and_school_publication_require_live_appointments(client, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import StaffAssignment, User
    from tests.test_aa_exam import BASE, TID, _seed, _hdr, _prepare_task_batch_for_exam

    ids = _seed(db_mode)
    school, college = _hdr(client, "school_admin01"), _hdr(client, "college_admin01")
    _prepare_task_batch_for_exam(client, school, ids["tt1"])
    created = client.post(f"{BASE}/exam/batches", headers=school,
        json={"batchName": "责任交接考试", "termId": str(ids["term"])})
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["batchId"]
    added = client.post(f"{BASE}/exam/batches/{bid}/courses", headers=school,
        json={"teachingTaskId": str(ids["tt1"])})
    assert added.status_code == 200, added.text
    cid = added.json()["data"]["examCourseId"]

    def confirm_action(headers):
        return client.get(f"{BASE}/exam/batches/{bid}/courses", headers=headers).json()["data"]["items"][0]["confirmAction"]

    def publish_action(headers):
        return client.get(f"{BASE}/exam/batches/{bid}", headers=headers).json()["data"]["publishAction"]

    assert confirm_action(college)["allowed"] is True
    assert confirm_action(school)["allowed"] is False
    assert publish_action(school)["allowed"] is False

    def expire(login, org_type, expired):
        with get_sessionmaker()() as db:
            uid = db.query(User.id).filter(User.tenant_id == TID, User.login_name == login).scalar()
            appointment = db.query(StaffAssignment).filter(StaffAssignment.tenant_id == TID,
                StaffAssignment.user_id == uid, StaffAssignment.org_type == org_type).one()
            appointment.expires_at = datetime(2020, 1, 2) if expired else None
            db.commit()

    assert client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=school,
        json={"action": "CONFIRM"}).status_code == 403
    expire("college_admin01", "COLLEGE", True)
    assert confirm_action(college)["allowed"] is False
    assert client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=college,
        json={"action": "CONFIRM"}).status_code == 403
    courses = client.get(f"{BASE}/exam/batches/{bid}/courses", headers=school).json()["data"]["items"]
    assert courses[0]["status"] == "PENDING_CONFIRM"
    expire("college_admin01", "COLLEGE", False)
    assert confirm_action(college)["allowed"] is True
    confirmed = client.post(f"{BASE}/exam/courses/{cid}/confirm", headers=college, json={"action": "CONFIRM"})
    assert confirmed.status_code == 200, confirmed.text
    assert confirm_action(college)["allowed"] is False
    assert client.put(f"{BASE}/exam/courses/{cid}/schedule", headers=school,
        json={"examDate": "2027-06-20", "startTime": "09:00", "endTime": "11:00", "durationMinutes": 120}).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/confirm-courses", headers=school).status_code == 200
    room = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=school,
        json={"classroomText": "A101", "capacity": 50})
    assert room.status_code == 200, room.text
    rid = room.json()["data"]["examRoomId"]
    assert client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=school,
        json={"studentIds": [str(ids["s1"]), str(ids["s2"])]}).status_code == 200
    assert client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=school,
        json={"teacherKey": "teacher_a", "teacherName": "甲老师", "role": "CHIEF"}).status_code == 200
    before = client.get(f"{BASE}/exam/batches/{bid}", headers=school).json()["data"]["status"]
    assert publish_action(school)["allowed"] is True
    assert publish_action(college)["allowed"] is False
    listed = client.get(f"{BASE}/exam/batches", headers=school).json()["data"]["items"]
    assert next(row for row in listed if row["batchId"] == bid)["publishAction"]["allowed"] is True
    expire("school_admin01", "SCHOOL", True)
    assert publish_action(school)["allowed"] is False
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=school).status_code == 403
    assert client.get(f"{BASE}/exam/batches/{bid}", headers=school).json()["data"]["status"] == before
    expire("school_admin01", "SCHOOL", False)
    assert publish_action(school)["allowed"] is True
    published = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=school)
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "PUBLISHED"
    assert publish_action(school)["allowed"] is False
    assert client.get(f"{BASE}/exam/batches/{bid}", headers=school).json()["data"]["status"] == "PUBLISHED"


def test_mysql_exam_scope_ignores_stale_student_college_and_rejects_foreign_course(db_mode, monkeypatch):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaExamCourse, AaExamBatch, AaExamIncident
    tid = 1000000000000000001
    monkeypatch.setattr(service, "_tid", lambda: tid)
    with get_sessionmaker()() as db:
        course = AaCourse(tenant_id=tid, course_code="V5-EXAM", course_name="跨院考务课程", owner_college_id=12)
        task_batch = AaTeachingTaskBatch(tenant_id=tid, term_id=91, college_id=34, batch_name="学生所在学院历史批次")
        exam_batch = AaExamBatch(tenant_id=tid, term_id=91, batch_name="跨院考试", status="DRAFT")
        db.add_all([course, task_batch, exam_batch])
        db.flush()
        task = AaTeachingTask(tenant_id=tid, batch_id=task_batch.id, course_id=course.id, status="READY")
        db.add(task)
        db.flush()
        exam = AaExamCourse(tenant_id=tid, batch_id=exam_batch.id, teaching_task_id=task.id,
                            course_id=course.id, college_id=34, status="PENDING_CONFIRM")
        db.add(exam)
        db.flush()
        assert service._course_college_id(db, exam) == 12
        owner = Row(scope_type="COLLEGE", college_ids={12})
        other = Row(scope_type="COLLEGE", college_ids={34})
        service._check_course_scope(db, owner, exam)
        with pytest.raises(Exception):
            service._check_course_scope(db, other, exam)
        assert db.scalar(select(AaExamBatch.id).where(AaExamBatch.id == exam_batch.id, service._batch_visibility(owner))) == exam_batch.id
        assert db.scalar(select(AaExamBatch.id).where(AaExamBatch.id == exam_batch.id, service._batch_visibility(other))) is None
        assert exam.college_id == 34  # 不回写历史审核事实。
        other_course = AaCourse(tenant_id=tid, course_code="V5-EXAM-OTHER", course_name="另一开课学院课程", owner_college_id=34)
        db.add(other_course)
        db.flush()
        other_exam = AaExamCourse(tenant_id=tid, batch_id=exam_batch.id, course_id=other_course.id, status="CONFIRMED")
        db.add(other_exam)
        db.flush()
        db.add_all([AaExamIncident(tenant_id=tid, exam_course_id=exam.id, student_id=901, incident_type="ABSENT", status="ACTIVE"),
                    AaExamIncident(tenant_id=tid, exam_course_id=other_exam.id, student_id=902, incident_type="ABSENT", status="ACTIVE")])
        db.flush()
        scoped_stats = service._batch_stats_calc(db, exam_batch, owner)
        assert scoped_stats == {"courseCount": 1, "confirmedCount": 0, "absentCount": 1, "violationCount": 0}
        assert service._batch_stats_calc(db, exam_batch, Row(scope_type="TENANT_ALL"))["courseCount"] == 2
        task.tenant_id = tid + 1
        db.flush()
        assert service._course_college_id(db, exam) is None
        task.tenant_id = tid
        course.owner_college_id = None
        db.flush()
        assert service._course_college_id(db, exam) == 34
        course.tenant_id = tid + 1
        db.flush()
        assert service._course_college_id(db, exam) is None
        with pytest.raises(Exception):
            service._check_course_scope(db, Row(scope_type="TENANT_ALL"), exam)
        db.rollback()
