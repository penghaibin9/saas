"""Selection input behavior with isolated collaborators; never opens a database."""
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_batch_command_service as command


@pytest.fixture
def command_context(monkeypatch):
    written = []
    db = SimpleNamespace(add=written.append, flush=lambda: None, commit=lambda: None)

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr(command._core, "session", session)
    monkeypatch.setattr(command._core, "_ctx", lambda *_: None)
    monkeypatch.setattr(command._core, "_require_manage_scope", lambda *_: None)
    monkeypatch.setattr(command._core, "_tid", lambda: 1)
    monkeypatch.setattr(command._core, "_audit", lambda *_: None)
    monkeypatch.setattr(command._core, "_batch_dto", lambda row: row)
    return written


@pytest.mark.parametrize("start,end", [
    ("invalid", None), (None, "invalid"),
    ("2026-10-29T10:00:00+08:00", "2026-10-29T02:00:00Z"),
    ("2026-10-29T10:00:00+08:00", "2026-10-29T01:59:59Z"),
])
def test_create_rejects_invalid_window_without_writing(command_context, start, end):
    with pytest.raises(AppException):
        command.create_batch({}, SimpleNamespace(batchName="输入检查", selectStartAt=start, selectEndAt=end))
    assert command_context == []


def test_create_normalizes_timezone_and_preserves_open_ended_window(command_context):
    body = SimpleNamespace(batchName="输入检查", selectStartAt="2026-10-29T10:00:00+08:00", selectEndAt=None, rule={"maxCredits": 0})
    row = command.create_batch({}, body)
    assert row.select_start_at == datetime(2026, 10, 29, 2)
    assert row.select_end_at is None
    assert len(command_context) == 1


@pytest.mark.parametrize("value", [-1, True, None, "abc", "NaN", float("nan"), float("inf"), {}, []])
def test_invalid_credit_limit_is_rejected_on_create_and_save(command_context, monkeypatch, value):
    body = SimpleNamespace(batchName="输入检查", rule={"maxCredits": value})
    with pytest.raises(AppException):
        command.create_batch({}, body)
    assert command_context == []
    batch = SimpleNamespace(id=1, status="DRAFT", rule_json='{"maxCredits": 12}')
    monkeypatch.setattr(command, "_lock_batch", lambda *_: batch)
    monkeypatch.setattr(command, "_guard_batch_writable", lambda *_: None)
    with pytest.raises(AppException):
        command.save_rule({}, 1, {"maxCredits": value})
    assert batch.rule_json == '{"maxCredits": 12}'


@pytest.mark.parametrize("value", [0, 0.5, 24, 60])
def test_existing_nonnegative_limits_and_other_rule_fields_survive(command_context, monkeypatch, value):
    import json
    batch = SimpleNamespace(id=1, status="PUBLISHED", rule_json=None)
    monkeypatch.setattr(command, "_lock_batch", lambda *_: batch)
    monkeypatch.setattr(command, "_guard_batch_writable", lambda *_: None)
    rule = {"maxCredits": value, "existingSetting": {"enabled": True}}
    command.save_rule({}, 1, rule)
    assert json.loads(batch.rule_json) == rule


def test_naive_input_uses_tenant_timezone(monkeypatch):
    from datetime import timezone, timedelta
    from app.core import timeutil
    monkeypatch.setattr(timeutil, "tenant_tz", lambda: timezone(timedelta(hours=8)))
    assert command._selection_datetime("2026-10-29T10:00", "开选时间") == datetime(2026, 10, 29, 2)


def test_rule_precondition_prevents_overwriting_another_writer(command_context, monkeypatch):
    batch = SimpleNamespace(id=1, status="DRAFT", rule_json='{"maxCredits": 18}')
    monkeypatch.setattr(command, "_lock_batch", lambda *_: batch)
    monkeypatch.setattr(command, "_guard_batch_writable", lambda *_: None)
    with pytest.raises(AppException, match="其他人员修改"):
        command.save_rule({}, 1, {"maxCredits": 20}, expected_rule={"maxCredits": 12})
    assert batch.rule_json == '{"maxCredits": 18}'
    command.save_rule({}, 1, {"maxCredits": 20}, expected_rule={"maxCredits": 18})
    assert batch.rule_json == '{"maxCredits": 20}'
