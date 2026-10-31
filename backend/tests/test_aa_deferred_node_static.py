"""缓考四级分别办理的静态行为测试，不连接数据库。"""
from types import SimpleNamespace as Row
from unittest.mock import MagicMock
import importlib

import pytest
from app.core.exceptions import AppException
service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_service")


@pytest.mark.parametrize("status", ["COUNSELOR_REVIEW", "TEACHER_CONFIRM", "COLLEGE_REVIEW"])
def test_school_cannot_take_over_previous_nodes(monkeypatch, status):
    monkeypatch.setattr(service, "_role", lambda: "ACADEMIC_ADMIN")
    ctx = Row(scope_type="TENANT_ALL", college_ids=set())
    with pytest.raises(AppException):
        service._check_defer_scope({}, MagicMock(), ctx, Row(status=status))


def test_school_only_handles_final_node(monkeypatch):
    monkeypatch.setattr(service, "_role", lambda: "ACADEMIC_ADMIN")
    service._check_defer_scope({}, MagicMock(), Row(scope_type="TENANT_ALL"), Row(status="ACADEMIC_FINAL"))


def test_college_actor_requires_offering_college_scope(monkeypatch):
    monkeypatch.setattr(service, "_role", lambda: "COLLEGE_ACADEMIC")
    monkeypatch.setattr(service, "_get_course", lambda *_: Row(id=1))
    guard = MagicMock()
    monkeypatch.setattr(service, "_check_course_scope", guard)
    service._check_defer_scope({}, MagicMock(), Row(scope_type="COLLEGE", college_ids={10}), Row(status="COLLEGE_REVIEW", exam_course_id=1))
    guard.assert_called_once()


def test_actions_require_both_relationship_and_node_permission(monkeypatch):
    row = Row(status="TEACHER_CONFIRM")
    monkeypatch.setattr(service, "_check_defer_scope", lambda *_: None)
    permission = MagicMock(side_effect=AppException("NO_PERMISSION", "无节点权限"))
    monkeypatch.setattr(service, "_require_defer_review_permission", permission)
    assert service._defer_allowed_actions({}, MagicMock(), Row(), row) == []
    permission.side_effect = None
    assert service._defer_allowed_actions({}, MagicMock(), Row(), row) == ["APPROVE", "RETURN", "REJECT"]
    assert service._defer_allowed_actions({}, MagicMock(), Row(), Row(status="APPROVED")) == []


def test_stale_version_is_rejected():
    with pytest.raises(AppException, match="发生变化"):
        service._require_defer_version(Row(version=2), 1)


def test_registered_defer_route_forwards_exact_identity_without_database(monkeypatch):
    import inspect
    from app.main import app
    from app.core.route_introspection import iter_effective_api_routes
    routes=[r for r in iter_effective_api_routes(app.routes) if getattr(r,"path",None)=="/api/v1/academic-affairs/deferred-exams" and "GET" in getattr(r,"methods",set())]
    assert len(routes)==1
    endpoint=getattr(routes[0],"original_route",routes[0]).endpoint
    assert "deferId" in inspect.signature(endpoint).parameters
    owner=importlib.import_module(endpoint.__module__)
    reader=MagicMock(return_value=([],0))
    monkeypatch.setattr(owner.exam_svc,"defer_list",reader)
    endpoint(status=None,page=1,pageSize=2,deferId=71,user={})
    assert reader.call_args.kwargs["defer_id"]==71


def test_defer_list_paginates_before_reading_rows(monkeypatch):
    from contextlib import contextmanager
    db=MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service,"session",session)
    monkeypatch.setattr(service,"_tid",lambda:1)
    monkeypatch.setattr(service,"_ctx",lambda *_:Row(scope_type="TENANT_ALL"))
    query=db.query.return_value.filter.return_value
    query.count.return_value=201
    query.order_by.return_value.offset.return_value.limit.return_value.all.return_value=[]
    rows,total=service.defer_list({},page=11,page_size=20)
    assert rows==[] and total==201
    query.all.assert_not_called()
    query.order_by.return_value.offset.assert_called_once_with(200)


def test_counselor_requires_current_student_and_owned_class(monkeypatch):
    monkeypatch.setattr(service,"_role",lambda:"COUNSELOR")
    monkeypatch.setattr(service,"_tid",lambda:1)
    db=MagicMock();ctx=Row(scope_type="CLASS",class_ids={10})
    db.query.return_value.filter.return_value.first.return_value=Row(class_id=10)
    service._check_defer_scope({},db,ctx,Row(status="COUNSELOR_REVIEW",student_id=1))
    clauses=db.query.return_value.filter.call_args.args
    assert any("is_deleted IS false" in str(clause) for clause in clauses)
    db.query.return_value.filter.return_value.first.return_value=Row(class_id=20)
    with pytest.raises(AppException):
        service._check_defer_scope({},db,ctx,Row(status="COUNSELOR_REVIEW",student_id=1))


def test_teacher_node_uses_exact_exam_teacher_relationship(monkeypatch):
    monkeypatch.setattr(service,"_role",lambda:"ACADEMIC_TEACHER")
    monkeypatch.setattr(service,"_derive_keys",lambda *_:{"teacher-a"})
    course=Row(teacher_key="teacher-a")
    monkeypatch.setattr(service,"_get_course",lambda *_:course)
    service._check_defer_scope({},MagicMock(),Row(scope_type="SELF"),Row(status="TEACHER_CONFIRM",exam_course_id=1))
    course.teacher_key="teacher-b"
    with pytest.raises(AppException):
        service._check_defer_scope({},MagicMock(),Row(scope_type="SELF"),Row(status="TEACHER_CONFIRM",exam_course_id=1))


@pytest.mark.parametrize("reason,version,ok",[("已根据退回意见补充说明",1,True),("短",1,False),("已根据退回意见补充说明",None,False),("已根据退回意见补充说明",0,False)])
def test_student_resubmit_updates_original_reason_with_version(monkeypatch,reason,version,ok):
    from contextlib import contextmanager
    import app.services.mobile_student_service as identity
    db=MagicMock()
    @contextmanager
    def session(): yield db
    row=Row(id=71,student_id=1,status="RETURNED",current_node="STUDENT_RESUBMIT",version=1,reason="旧说明")
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value=row
    monkeypatch.setattr(service,"session",session);monkeypatch.setattr(service,"_tid",lambda:1)
    monkeypatch.setattr(identity,"_require_student",lambda user:user);monkeypatch.setattr(identity,"resolve_student",lambda *_:Row(id=1))
    monkeypatch.setattr(service,"_defer_dto",lambda d:{"deferId":str(d.id),"version":d.version,"reason":d.reason})
    audit=MagicMock();monkeypatch.setattr(service,"_audit",audit)
    if ok:
        reply=service.defer_resubmit({},71,version,reason=reason)
        assert reply["reason"]==reason and row.status=="COUNSELOR_REVIEW" and row.version==2
        db.commit.assert_called_once();audit.assert_called_once()
    else:
        with pytest.raises(AppException): service.defer_resubmit({},71,version,reason=reason)
        assert row.reason=="旧说明" and row.status=="RETURNED"
        db.commit.assert_not_called();audit.assert_not_called()


def test_resubmit_bridge_forwards_student_explanation(monkeypatch):
    facade=importlib.import_module("app.modules.academic_affairs.services.academic_affairs_exam_facade")
    bridge=importlib.import_module("app.modules.academic_affairs.services.mobile_academic_affairs_facade")
    spy=MagicMock(return_value={"deferId":"71"})
    monkeypatch.setattr(service,"defer_resubmit",spy);monkeypatch.setattr(facade,"defer_resubmit",spy)
    bridge.exam_defer_resubmit_my({},71,{"expectedVersion":1,"reason":"已补充原申请的说明"})
    spy.assert_called_once_with({},71,1,reason="已补充原申请的说明")
