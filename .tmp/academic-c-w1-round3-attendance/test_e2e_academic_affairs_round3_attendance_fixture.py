from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "backend/scripts/e2e_academic_affairs_round3.py"
    spec = importlib.util.spec_from_file_location("e2e_academic_affairs_round3", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_attendance_candidate_payloads_use_only_executable_formal_patterns_and_parity():
    module = _module()
    options = {
        "termStartDate": "2026-03-02",
        "termEndDate": "2026-04-05",
        "items": [{
            "teachingTaskId": "101",
            "classId": "201",
            "taskStatus": "APPROVED",
            "formalOccurrenceReady": True,
            "formalSchedulePatterns": [{
                "scheduleItemId": "301",
                "scopeHeadVersion": 7,
                "weekday": 1,
                "slotNo": 2,
                "startWeek": 1,
                "endWeek": 5,
                "weekParity": "ODD",
            }],
        }, {
            "teachingTaskId": "102",
            "classId": "202",
            "taskStatus": "ASSIGNED",
            "formalOccurrenceReady": True,
            "formalSchedulePatterns": [{
                "scheduleItemId": "998",
                "weekday": 1,
                "slotNo": 9,
                "startWeek": 1,
                "endWeek": 5,
                "weekParity": "ALL",
            }],
        }, {
            "teachingTaskId": "103",
            "classId": "203",
            "taskStatus": "APPROVED",
            "formalOccurrenceReady": False,
            "formalSchedulePatterns": [{
                "scheduleItemId": "999",
                "weekday": 2,
                "slotNo": 3,
                "startWeek": 1,
                "endWeek": 5,
                "weekParity": "ALL",
            }],
        }],
    }
    candidates = module._attendance_candidate_payloads(options, today=date(2026, 3, 10))
    assert [row["payload"]["sessionDate"] for row in candidates] == [
        "2026-03-02", "2026-03-16", "2026-03-30",
    ]
    assert all(row["payload"]["teachingTaskId"] == "101" for row in candidates)
    assert all(row["payload"]["classId"] == "201" for row in candidates)
    assert all(row["payload"]["slotNo"] == 2 for row in candidates)
    assert all(row["payload"]["scheduleItemId"] == "301" for row in candidates)
    assert all(row["scheduleItemId"] == "301" for row in candidates)


def test_round3_source_does_not_hardcode_arbitrary_attendance_coordinate():
    source = (Path(__file__).resolve().parents[2] / "backend/scripts/e2e_academic_affairs_round3.py").read_text(encoding="utf-8")
    assert 'f"{MOB}/teacher/academic/attendance/class-options"' in source
    assert "formalOccurrenceReady" in source
    assert "formalSchedulePatterns" in source
    assert "allowed_task_statuses" in source
    assert "_attendance_candidate_payloads" in source
    assert '"slotNo": 10' not in source
    assert "date.today().isoformat()" not in source[source.index("# ── 3) 考勤提交"):source.index("# ── 4) 门户")]
