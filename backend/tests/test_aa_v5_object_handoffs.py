"""对象责任附加不把查看者当办理人，并保留正式读入口的数据范围门禁。"""
from contextlib import contextmanager
from types import SimpleNamespace as Row
from unittest.mock import MagicMock
import importlib

import pytest

from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility


def test_program_responsibility_switches_between_major_college_and_school(monkeypatch):
    org = MagicMock(return_value={"resolved": True})
    school = MagicMock(return_value={"resolved": True})
    monkeypatch.setattr(responsibility, "resolve_organization", org)
    monkeypatch.setattr(responsibility, "resolve_school", school)
    monkeypatch.setattr(responsibility, "_tid", lambda: 1)
    db = MagicMock()
    db.scalar.return_value = Row(college_id=12)
    responsibility.resolve_program(db, Row(status="RETURNED", major_id=3))
    assert org.call_args.args[1:3] == ("MAJOR", 3)
    responsibility.resolve_program(db, Row(status="COLLEGE_REVIEW", major_id=3))
    assert org.call_args.args[1:3] == ("COLLEGE", 12)
    responsibility.resolve_program(db, Row(status="ACADEMIC_REVIEW", major_id=3))
    assert school.call_args.kwargs == {"permission_code": "academicAffairs.program.review", "cache": None}


def test_selection_detail_carries_school_handoff_after_existing_visibility_check(monkeypatch):
    service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_selection_read_core_service")
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service._core, "session", session)
    monkeypatch.setattr(service._core, "_ctx", lambda user, db: Row(scope_type="TENANT_ALL"))
    monkeypatch.setattr(service._core, "_get_batch", lambda db, bid: Row(id=bid, status="CLOSED"))
    monkeypatch.setattr(service._core, "_batch_dto", lambda batch: {"batchId": str(batch.id)})
    actor = {"resolved": True, "assigneeUserIds": ["99"], "assigneeNames": ["校级责任人"]}
    school = MagicMock(return_value=actor)
    monkeypatch.setattr(responsibility, "resolve_school", school)
    result = service.get_batch({"userId": "viewer"}, 9007199254740993)
    assert result["batchId"] == "9007199254740993"
    assert result["responsibility"] == actor
    assert result["nextStep"]["code"] == "LOCKED"
    def denied(*args):
        raise ValueError("范围拒绝")
    monkeypatch.setattr(service, "_require_batch_visible", denied)
    with pytest.raises(ValueError, match="范围拒绝"):
        service.get_batch({}, 1)
    assert school.call_count == 1


def test_schedule_summary_denies_foreign_or_schoolwide_batch_before_projection(monkeypatch):
    service = importlib.import_module("app.modules.academic_affairs.services.academic_affairs_scheduling_public_service")
    db = MagicMock()
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(service._base._base, "session", session)
    monkeypatch.setattr(service._base._base, "_tid", lambda: 1)
    monkeypatch.setattr(service._base._base, "_ctx", lambda user, db: Row(scope_type="COLLEGE", college_ids={12}))
    gate = MagicMock()
    monkeypatch.setattr(service.gate_service, "evaluate", gate)
    for college_id in (34, None):
        db.query.return_value.filter.return_value.first.return_value = Row(id=1, college_id=college_id)
        with pytest.raises(Exception, match="当前身份"):
            service.summary({}, 1)
    gate.assert_not_called()
