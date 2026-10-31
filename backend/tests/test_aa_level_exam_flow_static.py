"""等级考试无数据库行为检查，数据库锁语义另行验收。"""
from contextlib import contextmanager
from types import SimpleNamespace as Row
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_level_exam_service as service


def setup_service(monkeypatch, *, pass_line=0, status="CLOSED"):
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    exam = Row(id=1, status=status, pass_line=pass_line)
    reg = Row(id=2, exam_id=1, student_id=3, student_no="TEST", student_name="虚构学生", fee_status="PAID",
              score=None, result=None, cert_no=None, status="REGISTERED")
    monkeypatch.setattr(service, "session", session)
    monkeypatch.setattr(service, "_require_school", lambda *_: None)
    monkeypatch.setattr(service, "_locked_registration", lambda *_: (exam, reg))
    monkeypatch.setattr(service, "_audit", MagicMock())
    return db, reg


def test_zero_passline_uses_score_judgement(monkeypatch):
    db, reg = setup_service(monkeypatch)
    result = service.enter_result({}, 2, Row(score=0, result=None, certNo=None))
    assert result["result"] == "PASS" and reg.score == 0
    db.commit.assert_called_once()


def test_scored_exam_cannot_skip_score_by_sending_pass(monkeypatch):
    db, reg = setup_service(monkeypatch, pass_line=425)
    with pytest.raises(AppException, match="请填写分数"):
        service.enter_result({}, 2, Row(score=None, result="PASS"))
    assert reg.status == "REGISTERED"
    db.commit.assert_not_called()


def test_result_only_exam_keeps_existing_conclusion_flow(monkeypatch):
    _db, reg = setup_service(monkeypatch, pass_line=None)
    result = service.enter_result({}, 2, Row(score=None, result="PASS", certNo="TEST-CERT"))
    assert result["certNo"] == "TEST-CERT" and reg.status == "SCORED"


def test_open_exam_rejects_early_score(monkeypatch):
    db, _reg = setup_service(monkeypatch, status="OPEN")
    with pytest.raises(AppException, match="先截止报名"):
        service.enter_result({}, 2, Row(score=90))
    db.commit.assert_not_called()


@pytest.mark.parametrize("page,size", [(0, 20), (1, 201), (True, 20), (1, -1)])
def test_registration_page_rejects_invalid_bounds(page, size):
    with pytest.raises(AppException):
        service.list_regs({}, 1, page=page, page_size=size)


def test_registration_page_limits_in_query_before_materialization(monkeypatch):
    db, _reg = setup_service(monkeypatch)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "_get_exam", lambda *_: Row(id=1))
    query = db.query.return_value.filter.return_value
    query.count.return_value = 201
    page_query = query.order_by.return_value.offset.return_value.limit.return_value
    page_query.all.return_value = []
    rows, total = service.list_regs({}, 1, page=11, page_size=20)
    assert rows == [] and total == 201
    query.order_by.return_value.offset.assert_called_once_with(200)
    query.order_by.return_value.offset.return_value.limit.assert_called_once_with(20)
    query.all.assert_not_called()
