"""INT Program stable-series dirty-data inventory contracts."""
from __future__ import annotations

from app.modules.academic_affairs.services.academic_affairs_program_series_inventory import (
    inventory_program_series,
)


def _row(program_id, tenant_id, version, *, prev=None, major=10, grade="2026", name=None):
    return {
        "programId": program_id,
        "tenantId": tenant_id,
        "majorId": major,
        "gradeYear": grade,
        "version": version,
        "prevVersionId": prev,
        "programName": name or f"方案-{program_id}",
    }


def _codes(result):
    return {item["code"] for item in result["blockers"]}


def test_same_major_grade_version_independent_programs_remain_distinct_series():
    result = inventory_program_series([
        _row(101, 1, 1, name="通用方案"),
        _row(202, 1, 1, name="班级特例方案"),
    ])

    assert result["migrationPreflightSafe"] is True
    assert result["blockerCount"] == 0
    assert result["rootCount"] == 2
    assert {(item["programId"], item["seriesKey"]) for item in result["proposedBackfill"]} == {
        (101, "LEGACY-101"),
        (202, "LEGACY-202"),
    }


def test_linear_versions_share_root_series_without_using_program_name():
    result = inventory_program_series([
        _row(11, 7, 1, name="原名"),
        _row(12, 7, 2, prev=11, name="改名后的显示名"),
        _row(13, 7, 3, prev=12, name="再次改名"),
    ])

    assert result["migrationPreflightSafe"] is True
    assert [item["seriesKey"] for item in result["proposedBackfill"]] == [
        "LEGACY-11", "LEGACY-11", "LEGACY-11"
    ]
    assert [item["version"] for item in result["proposedBackfill"]] == [1, 2, 3]


def test_missing_parent_and_non_v1_root_fail_closed_with_no_partial_backfill():
    result = inventory_program_series([
        _row(21, 1, 2, prev=999),
        _row(31, 1, 3),
    ])

    assert result["migrationPreflightSafe"] is False
    assert result["proposedBackfill"] == []
    assert {"PROGRAM_PARENT_MISSING", "PROGRAM_ROOT_NOT_V1"}.issubset(_codes(result))


def test_fork_cycle_and_cross_tenant_parent_are_blockers():
    fork = inventory_program_series([
        _row(1, 1, 1),
        _row(2, 1, 2, prev=1),
        _row(3, 1, 2, prev=1),
    ])
    assert fork["migrationPreflightSafe"] is False
    assert "PROGRAM_VERSION_FORK" in _codes(fork)

    cycle = inventory_program_series([
        _row(10, 1, 1, prev=11),
        _row(11, 1, 2, prev=10),
    ])
    assert cycle["migrationPreflightSafe"] is False
    assert "PROGRAM_VERSION_CYCLE" in _codes(cycle)

    cross_tenant = inventory_program_series([
        _row(41, 1, 1),
        _row(42, 2, 2, prev=41),
    ])
    assert cross_tenant["migrationPreflightSafe"] is False
    assert "PROGRAM_PARENT_CROSS_TENANT" in _codes(cross_tenant)


def test_version_gap_and_series_scope_drift_fail_closed():
    gap = inventory_program_series([
        _row(51, 1, 1),
        _row(52, 1, 3, prev=51),
    ])
    assert gap["migrationPreflightSafe"] is False
    assert "PROGRAM_VERSION_NOT_DIRECT_SUCCESSOR" in _codes(gap)

    drift = inventory_program_series([
        _row(61, 1, 1, major=10, grade="2026"),
        _row(62, 1, 2, prev=61, major=11, grade="2027"),
    ])
    assert drift["migrationPreflightSafe"] is False
    assert "PROGRAM_SERIES_SCOPE_DRIFT" in _codes(drift)


def test_bad_input_never_produces_backfill():
    result = inventory_program_series([
        {"programId": "bad", "tenantId": 1, "version": 1},
        _row(71, 1, 1),
    ])

    assert result["migrationPreflightSafe"] is False
    assert result["proposedBackfill"] == []
    assert "PROGRAM_ROW_INVALID" in _codes(result)
