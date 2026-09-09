"""Contract tests for the read-only Academic V8.1 20K evidence probe."""
from __future__ import annotations

from scripts import audit_academic_v81_20k_performance as probe


def test_probe_covers_every_authority_scale_category_and_is_read_only():
    expected = {
        "dashboard/task-queue",
        "four-end-projection",
        "schedule",
        "registration",
        "selection",
        "exam",
        "grade",
        "warning",
        "formation",
        "archive",
        "stats",
    }
    assert expected.issubset({case.category for case in probe.PROBES})

    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "REPLACE ", "TRUNCATE ", "ALTER ", "DROP ")
    for case in probe.PROBES:
        normalized = " ".join(case.sql.upper().split())
        assert normalized.startswith("SELECT ")
        assert not any(token in normalized for token in forbidden)


def test_every_page_probe_has_a_literal_limit_and_scan_budget():
    for case in probe.PROBES:
        if case.page_limit is None:
            continue
        normalized = " ".join(case.sql.upper().split())
        assert f"LIMIT {case.page_limit}" in normalized
        assert case.scan_budget_rows is not None
        assert case.scan_budget_rows >= case.page_limit


def test_percentile_and_session_counter_delta_are_deterministic():
    assert probe._percentile([9.0, 1.0, 3.0, 5.0, 7.0], 0.50) == 5.0
    assert probe._percentile([9.0, 1.0, 3.0, 5.0, 7.0], 0.95) == 9.0
    assert probe._delta({"Handler_read_next": 121}, {"Handler_read_next": 21}) == {
        "Handler_read_next": 100
    }


def test_probe_reuses_repository_latency_and_payload_policies():
    assert probe.LATENCY_P95_LIMIT_MS == 1_000.0
    assert probe.PAYLOAD_LIMIT_BYTES == 32 * 1024
    assert probe.RUNS >= 20
