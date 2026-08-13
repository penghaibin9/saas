"""D6-U1：选课锁定不得在 TeachingRoster wrapper 重复全量扫描选课记录。"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from app.modules.academic_affairs.services import academic_affairs_teaching_roster_service as roster


class _CourseQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.queried_models = []

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        self.queried_models.append(name)
        if name != "AaSelectionCourse":
            raise AssertionError(f"wrapper 不得再次 materialize {name}")
        return _CourseQuery(self.rows)


def test_validate_selection_lock_reuses_canonical_selected_count(monkeypatch):
    monkeypatch.setattr(
        roster._core,
        "validate_selection_lock",
        lambda _db, _batch: {
            "valid": True,
            "issues": [],
            "selectedRecordCount": 2,
            "taskStudentCounts": {},
        },
    )
    rows = [
        SimpleNamespace(id=11, status="OPEN", selected_count=0, min_capacity=0),
        SimpleNamespace(id=12, status="OPEN", selected_count=2, min_capacity=3),
        SimpleNamespace(id=13, status="COURSE_CANCELLED", selected_count=0, min_capacity=20),
    ]
    db = _Db(rows)

    result = roster.validate_selection_lock(db, SimpleNamespace(id=7))

    assert db.queried_models == ["AaSelectionCourse"]
    assert result["batchId"] == "7"
    assert result["valid"] is False
    assert [issue["code"] for issue in result["issues"]] == [
        "EMPTY_OPEN_COURSE",
        "BELOW_MIN_CAPACITY",
    ]


def test_validate_selection_lock_source_has_no_second_record_scan():
    source = inspect.getsource(roster.validate_selection_lock)

    assert "AaSelectionRecord" not in source
    assert "selected_count" in source
    assert "_core.validate_selection_lock(db, batch)" in source
