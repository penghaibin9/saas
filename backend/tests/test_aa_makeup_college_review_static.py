"""无数据库行为回归；不能代替隔离 MySQL 的并发和持久化验收。"""
from contextlib import contextmanager
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_makeup_review_service as review
from app.modules.academic_affairs.services import academic_affairs_makeup_service as service


def record(row_id=1, college=10, score=72):
    return Row(id=row_id, review_college_id=college, college_reviewed_by=None, college_reviewed_at=None,
               status="SCORED" if score is not None else "PENDING_EXAM", final_score=score)


def test_college_can_finish_own_review_while_other_college_is_unscored():
    own, other = record(), record(2, 20, None)
    changed = review.approve_rows([(own, None, 10), (other, None, 20)], {10}, "actor-1")
    assert changed == [own] and review.reviewed(own)
    assert not review.reviewed(other)
    with pytest.raises(AppException):
        review.require_complete([own, other])


def test_review_is_idempotent_and_keeps_original_actor_and_time():
    own = record()
    rows = [(own, None, 10)]
    review.approve_rows(rows, {10}, "actor-1")
    before = own.college_reviewed_at
    assert review.approve_rows(rows, {10}, "actor-2") == []
    assert own.college_reviewed_by == "actor-1" and own.college_reviewed_at == before


@pytest.mark.parametrize("scope,actor", [({20}, "actor"), ({10}, "")])
def test_no_scope_or_unknown_actor_never_writes_review(scope, actor):
    own = record()
    with pytest.raises(AppException):
        review.approve_rows([(own, None, 10)], scope, actor)
    assert not review.reviewed(own)


def test_unscored_row_blocks_entire_own_college_before_any_mutation():
    ready, missing = record(), record(2, 10, None)
    with pytest.raises(AppException):
        review.approve_rows([(ready, None, 10), (missing, None, 10)], {10}, "actor")
    assert not review.reviewed(ready)


def test_zero_score_is_valid_and_school_gate_requires_every_college():
    a, b = record(score=0), record(2, 20)
    rows = [(a, None, 10), (b, None, 20)]
    review.approve_rows(rows, {10}, "a")
    with pytest.raises(AppException):
        review.require_complete([a, b])
    review.approve_rows(rows, {20}, "b")
    review.require_complete([a, b])


def test_historical_batch_status_cannot_substitute_for_review_facts():
    with pytest.raises(AppException):
        review.require_complete([record()])
    with pytest.raises(AppException):
        review.require_complete([])


def test_query_filters_offering_college_and_tenant_before_pagination(monkeypatch):
    monkeypatch.setattr(review.core, "_tid", lambda: 99)
    with Session() as db:
        q = review.scoped_records(db, Row(scope_type="COLLEGE", college_ids={10})).limit(20).offset(20)
        sql = str(q.statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "t_acad_makeup.tenant_id = 99" in sql
    assert "coalesce(t_acad_makeup.review_college_id, t_aa_course.owner_college_id, t_aa_teaching_task_batch.college_id) IN (10)" in sql
    assert "LIMIT 20, 20" in sql
    assert "t_student_profile.college_id" not in sql


def service_fixture(monkeypatch, scope="COLLEGE"):
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service._core, "session", session)
    monkeypatch.setattr(service._core, "_ctx", lambda *_: Row(scope_type=scope, college_ids={10}))
    monkeypatch.setattr(service._core, "_tid", lambda: 99)
    monkeypatch.setattr(service, "get_current_user_ctx", lambda: {"userId": "actor-1"})
    monkeypatch.setattr("app.core.permissions.has_permission", lambda *_: True)
    return db


def test_school_cannot_use_college_command_even_with_permission(monkeypatch):
    db = service_fixture(monkeypatch, "TENANT_ALL")
    with pytest.raises(AppException, match="不能代审"):
        service.college_review_scores({}, 1, 0)
    db.commit.assert_not_called()
    db.query.assert_not_called()


@pytest.mark.parametrize("other_reviewed,expected", [(False, "SCORING"), (True, "REVIEWED")])
def test_public_command_only_advances_after_last_college(monkeypatch, other_reviewed, expected):
    db = service_fixture(monkeypatch)
    own, other = record(), record(2, 20)
    if other_reviewed:
        review.approve_rows([(other, None, 20)], {20}, "other")
    batch = Row(id=1, status="SCORING", score_version=0)
    lock = MagicMock(return_value=batch)
    monkeypatch.setattr(service._core, "_get_mb", lock)
    monkeypatch.setattr(service, "_guard_batch", lambda *_: None)
    monkeypatch.setattr(service._core, "_mb_dto", lambda row: {"batchId": str(row.id), "status": row.status})
    audit = MagicMock()
    monkeypatch.setattr(service._core, "_audit", audit)
    query = MagicMock()
    query.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [(own, None, 10), (other, None, 20)]
    monkeypatch.setattr(review, "record_query", lambda *_: (query, None))
    monkeypatch.setattr(review, "summary", lambda *_: {1: {"reviewTotal": 1, "reviewedCount": 1}})
    reply = service.college_review_scores({}, 1, 0)
    assert reply["status"] == expected and reply["reviewedCount"] == 1
    lock.assert_called_once_with(db, 1, for_update=True)
    audit.assert_called_once()
    db.commit.assert_called_once()


def test_school_finish_rejects_legacy_reviewed_batch_without_evidence(monkeypatch):
    db = service_fixture(monkeypatch, "TENANT_ALL")
    monkeypatch.setattr(service._core, "_get_mb", lambda *_args, **_kw: Row(id=1, status="REVIEWED"))
    monkeypatch.setattr(service, "_guard_batch", lambda *_: None)
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [record()]
    with pytest.raises(AppException, match="全部开课学院"):
        service.finish_makeup_batch({}, 1)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_review_rejects_score_changed_after_page_was_read(monkeypatch):
    db = service_fixture(monkeypatch)
    monkeypatch.setattr(service._core, "_get_mb", lambda *_args, **_kw: Row(id=1, status="SCORING", score_version=2))
    monkeypatch.setattr(service, "_guard_batch", lambda *_: None)
    with pytest.raises(AppException, match="成绩或审核进度已变化"):
        service.college_review_scores({}, 1, 1)
    db.query.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("kind,raw,expected", [("DEFERRED",88,88),("MAKEUP",88,60),("DEFERRED",0,0)])
def test_finish_keeps_deferred_actual_score_but_caps_makeup(monkeypatch,kind,raw,expected):
    from app.models import AcademicGrade
    db=service_fixture(monkeypatch,"TENANT_ALL")
    batch=Row(id=1,batch_name="虚构批次",status="REVIEWED",score_rule="CAP60",term_code="2026-2027-1",score_version=1,exam_batch_ref=None,published_at=None)
    row=record(score=raw);row.kind=kind;row.acad_student_id=9
    review.approve_rows([(row,None,10)],{10},"reviewer")
    monkeypatch.setattr(service._core,"_get_mb",lambda *_args,**_kw:batch)
    monkeypatch.setattr(service,"_guard_batch",lambda *_:None)
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value=[row]
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value=None
    db.query.return_value.filter.return_value.first.return_value=None
    identity={"courseId":1,"courseCode":"C1","courseVersion":1,"attemptNo":1,"gradeTaskId":None,"sourceBizType":kind,"sourceBizId":1,"teachingTaskId":None,"teachingClassId":None,"rosterVersionId":None,"courseName":"虚构课程","nature":"REQUIRED","credit":2,"examType":kind,"gradeSource":kind}
    monkeypatch.setattr(service,"_deferred_identity",lambda *_:identity)
    monkeypatch.setattr(service,"_regular_origin",lambda *_:identity)
    monkeypatch.setattr(service,"freeze_effective_grade_policy",lambda *_args,**_kw:None)
    monkeypatch.setattr(service._core,"_audit",lambda *_args:None)
    service.finish_makeup_batch({},1)
    grades=[call.args[0] for call in db.add.call_args_list if isinstance(call.args[0],AcademicGrade)]
    assert len(grades)==1 and grades[0].score==expected
    assert row.status=="FINISHED"


@pytest.mark.parametrize("targets,expected", [([101],"901"),([102],None),([101,101],None)])
def test_deferred_pool_only_exposes_unique_exact_merge_link(monkeypatch,targets,expected):
    db=service_fixture(monkeypatch,"TENANT_ALL")
    d=Row(id=71,student_id=1,student_name="虚构学生",exam_course_id=2,course_name="虚构课程",next_batch_ref="101")
    q=MagicMock();q.filter.return_value=q;q.count.return_value=1
    q.order_by.return_value.offset.return_value.limit.return_value.all.return_value=[d]
    links=MagicMock();links.filter.return_value.all.return_value=[Row(source_biz_id=71,id=901+i,batch_id=target) for i,target in enumerate(targets)]
    db.query.side_effect=[q,links]
    rows,total=service.deferred_pool({},defer_id=71)
    assert total==1 and rows[0]["makeupId"]==expected
