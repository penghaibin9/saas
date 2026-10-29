"""Management behavior with isolated collaborators, no database writes."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_batch_command_service as command
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as final


@pytest.fixture
def draft(monkeypatch):
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    batch = SimpleNamespace(id=1, term_id=52, status="DRAFT", version=1, batch_name="旧名称", apply_scope_json=None)
    monkeypatch.setattr(command._core, "session", session)
    monkeypatch.setattr(command._core, "_ctx", lambda *_: None)
    monkeypatch.setattr(command._core, "_require_manage_scope", lambda *_: None)
    monkeypatch.setattr(command._core, "_tid", lambda: 1)
    monkeypatch.setattr(command._core, "_audit", lambda *_: None)
    monkeypatch.setattr(command._core, "_batch_dto", lambda row: {"version": row.version})
    monkeypatch.setattr(command, "_lock_batch", lambda *_: batch)
    monkeypatch.setattr(command, "_guard_batch_writable", lambda *_: None)
    body = SimpleNamespace(batchName=" 修改名称 ", selectStartAt=None, selectEndAt=None, applyScope=None, remark="保留备注", expectedVersion=1)
    return db, batch, body


def test_update_draft_keeps_term_and_increments_version(draft):
    db, batch, body = draft
    batch.term_id = 52
    assert command.update_draft({}, 1, body)["version"] == 2
    assert batch.batch_name == "修改名称" and batch.term_id == 52
    db.commit.assert_called_once()


@pytest.mark.parametrize("state,version", [("PUBLISHED",1),("LOCKED",1),("DRAFT",2)])
def test_draft_rejects_state_or_version_changes_without_commit(draft, state, version):
    db, batch, body = draft; batch.status=state; batch.version=version
    with pytest.raises(AppException): command.update_draft({},1,body)
    assert batch.batch_name == "旧名称"
    db.commit.assert_not_called()


def test_draft_rejects_foreign_or_deleted_class(draft):
    db, batch, body = draft; body.applyScope={"classIds":["99"]}
    db.query.return_value.filter.return_value.all.return_value=[]
    with pytest.raises(AppException): command.update_draft({},1,body)
    assert batch.version == 1
    db.commit.assert_not_called()


def test_termless_draft_can_bind_but_existing_term_cannot_change(draft, monkeypatch):
    db, batch, body = draft
    body.termId = "53"
    with pytest.raises(AppException): command.update_draft({},1,body)
    db.commit.assert_not_called()
    batch.term_id = None
    monkeypatch.setattr(command,"_require_term_reference_writable",lambda *_,**__: SimpleNamespace(id=53))
    command.update_draft({},1,body)
    assert batch.term_id == 53


@pytest.mark.parametrize("downstream,expected", [(0,True),(1,False)])
def test_adjustment_read_checks_downstream_and_never_commits(monkeypatch, downstream, expected):
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as consumer
    from app.modules.academic_affairs.services import academic_affairs_task_execution_authority as authority
    rows=[SimpleNamespace(id=7,selection_course_id=8,batch_id=9,status="LOCKED"), SimpleNamespace(id=8,batch_id=9,teaching_task_id=10), SimpleNamespace(id=9,status="LOCKED")]
    db=MagicMock(); db.query.side_effect=[SimpleNamespace(filter=lambda *_, row=row: SimpleNamespace(first=lambda:row)) for row in rows]
    @contextmanager
    def session(): yield db
    monkeypatch.setattr(final._base._core,"session",session)
    monkeypatch.setattr(final._base._core,"_ctx",lambda *_:None)
    monkeypatch.setattr(final._base._core,"_require_manage_scope",lambda *_:None)
    monkeypatch.setattr(final._base._core,"_tid",lambda:1)
    monkeypatch.setattr(final._base._core,"_record_dto",lambda _: {"recordId":"7"})
    monkeypatch.setattr(final._base,"_guard_batch_writable",lambda *_:None)
    monkeypatch.setattr(consumer,"consumer_counts",lambda *_,**__: {"TOTAL":downstream})
    monkeypatch.setattr(authority,"require_independent_task",lambda *_:None)
    result=final.adjustment_detail({},7)
    assert result["canAdjust"] is expected
    assert bool(result["blockedReason"]) is not expected
    db.commit.assert_not_called()


@pytest.mark.parametrize("latest_status", ["LOCKED", "DROPPED"])
def test_adjustment_uses_course_batch_record_lock_order_and_rereads_state(monkeypatch, latest_status):
    from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as consumer
    record=SimpleNamespace(id=7,selection_course_id=8,batch_id=9,status=latest_status)
    course=SimpleNamespace(id=8,teaching_task_id=10)
    batch=SimpleNamespace(id=9,status="LOCKED")
    locks=[]; queries=[]
    for name,row in [("snapshot",record),("course",course),("batch",batch),("record",record)]:
        query=MagicMock();query.filter.return_value=query;query.populate_existing.return_value=query
        query.with_for_update.side_effect=lambda q=query,n=name: (locks.append(n),q)[1]
        query.first.return_value=row;queries.append(query)
    db=MagicMock();db.query.side_effect=queries
    @contextmanager
    def session(): yield db
    monkeypatch.setattr(final._base._core,"session",session)
    monkeypatch.setattr(final._base._core,"_ctx",lambda *_:None)
    monkeypatch.setattr(final._base._core,"_require_manage_scope",lambda *_:None)
    monkeypatch.setattr(final._base._core,"_tid",lambda:1)
    monkeypatch.setattr(final._base,"_guard_batch_writable",lambda *_:None)
    from app.modules.academic_affairs.services import academic_affairs_task_execution_authority as authority
    monkeypatch.setattr(authority,"require_independent_task",lambda *_:None)
    monkeypatch.setattr(consumer,"consumer_counts",lambda *_,**__: {"TOTAL":1})
    with pytest.raises(AppException): final.adjust_record({},7,"经核对申请人工退课")
    assert locks == ["course","batch","record"]
    queries[3].populate_existing.assert_called_once()
    db.commit.assert_not_called()
