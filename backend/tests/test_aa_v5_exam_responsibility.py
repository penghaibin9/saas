"""开课责任动态范围：规则检查与由主控串行执行的真实 MySQL 回归。"""
from types import SimpleNamespace as Row
from unittest.mock import MagicMock
import importlib
from contextlib import contextmanager

import pytest

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
