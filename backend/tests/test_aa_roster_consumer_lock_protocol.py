"""D6/R9：消费者冻结与正式名单换版必须共用 TeachingClass 锁序。"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException


svc = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_roster_consumer_service"
)
_SERVICES = Path(__file__).resolve().parents[1] / "app/modules/academic_affairs/services"


def _roster(version_id: int):
    return {
        "ready": True,
        "source": "SELECTION_LOCK",
        "teachingClassId": "20",
        "rosterVersionId": str(version_id),
        "rosterVersionNo": version_id,
        "rosterHash": f"hash-{version_id}",
        "memberCount": 1,
        "studentIds": [101],
    }


def _snapshot(version_id: int):
    return SimpleNamespace(
        id=90,
        snapshot_version=1,
        consumer_type="ATTENDANCE_SESSION",
        consumer_id=91,
        teaching_task_id=30,
        teaching_class_id=20,
        roster_version_id=version_id,
        roster_version_no=version_id,
        roster_hash=f"hash-{version_id}",
        member_count=1,
        student_ids_json="[101]",
        roster_source="SELECTION_LOCK",
        status="ACTIVE",
        captured_at=None,
        captured_by="tester",
    )


def test_freeze_locks_and_revalidates_before_consumer_rows(monkeypatch):
    events = []
    current = _roster(7)
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_lock_teaching_class_for_task",
        lambda _db, task_id, create_if_missing=False: events.append(
            ("lock", task_id, create_if_missing)
        ) or SimpleNamespace(id=20),
    )
    monkeypatch.setattr(
        svc,
        "resolve_versioned_roster",
        lambda _db, task_id: events.append(("resolve", task_id)) or current,
    )
    monkeypatch.setattr(
        svc,
        "_consumer_rows",
        lambda _db, kind, consumer_id, lock=False: events.append(("rows", lock)) or [_snapshot(7)],
    )

    result = svc.freeze_consumer_snapshot(
        object(),
        "ATTENDANCE_SESSION",
        91,
        30,
        roster=dict(current),
    )

    assert events == [("lock", 30, True), ("resolve", 30), ("rows", True)]
    assert result["rosterVersionId"] == "7"
    assert result["created"] is False


def test_freeze_rejects_stale_preloaded_roster_before_snapshot_rows(monkeypatch):
    events = []
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_lock_teaching_class_for_task",
        lambda _db, task_id, create_if_missing=False: events.append(
            ("lock", task_id, create_if_missing)
        ) or SimpleNamespace(id=20),
    )
    monkeypatch.setattr(
        svc,
        "resolve_versioned_roster",
        lambda _db, task_id: events.append(("resolve", task_id)) or _roster(8),
    )
    monkeypatch.setattr(
        svc,
        "_consumer_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stale roster must fail before consumer rows")
        ),
    )

    with pytest.raises(AppException) as exc:
        svc.freeze_consumer_snapshot(
            object(),
            "GRADE_TASK",
            92,
            30,
            roster=_roster(7),
        )

    assert events == [("lock", 30, True), ("resolve", 30)]
    assert "名单已在业务冻结前换版" in str(exc.value)


class _CountQuery:
    def __init__(self, events):
        self.events = events

    def filter(self, *_args):
        return self

    def group_by(self, *_args):
        return self

    def all(self):
        return []


class _CountDb:
    def __init__(self, events):
        self.events = events

    def query(self, *_args):
        self.events.append(("query", None))
        return _CountQuery(self.events)


def test_teaching_task_consumer_count_locks_existing_class_before_query(monkeypatch):
    events = []
    monkeypatch.setattr(svc, "_tid", lambda: 1)
    monkeypatch.setattr(
        svc,
        "_lock_teaching_class_for_task",
        lambda _db, task_id, create_if_missing=False: events.append(
            ("lock", task_id, create_if_missing)
        ) or SimpleNamespace(id=20),
    )

    result = svc.consumer_counts(_CountDb(events), teaching_task_id=30)

    assert events[:2] == [("lock", 30, False), ("query", None)]
    assert result["TOTAL"] == 0


def test_r9_lock_helper_preserves_canonical_order_and_no_write_default():
    source = (_SERVICES / "academic_affairs_roster_consumer_service.py").read_text(encoding="utf-8")
    start = source.index("def _lock_teaching_class_for_task")
    end = source.index("\ndef _same_resolved_roster", start)
    block = source[start:end]

    assert "AaTeachingClass" in block
    assert ".with_for_update().first()" in block
    assert "if row or not create_if_missing" in block
    assert "ensure_teaching_class_for_task" in block
    assert "AaTeachingClassRosterVersion" not in block
