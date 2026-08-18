"""Baseline migration must share the canonical Program series-key grammar."""
from __future__ import annotations

import pytest


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_baseline_migration_policy as policy
    return policy


def _evidence(series_key: str) -> dict:
    return {
        "programSeriesKey": series_key,
        "baselineVersion": 3,
        "sourceSystem": "LEGACY_SIS",
        "sourceRecordId": "program-2026-soft-v3",
        "sourceApprovalEvidence": {
            "decision": "APPROVED",
            "evidenceRef": "legacy-approval-8891",
            "approvedByRef": "legacy-user-1008",
            "approvedAt": "2026-01-10T09:30:00+08:00",
        },
        "effectiveAt": "2026-02-01T00:00:00+08:00",
        "auditTicket": "MIG-2026-00017",
        "migrationReason": "旧系统只保留已批准当前快照",
    }


def test_baseline_series_key_uses_same_normalization_as_program_v2():
    result = _policy().build_program_baseline_migration_policy(_evidence("cs-soft.v3"))
    assert result["programSeriesKey"] == "CS-SOFT.V3"


@pytest.mark.parametrize(
    "series_key",
    [
        "中文方案",
        "BAD KEY",
        "_LEADING_UNDERSCORE",
        "A" * 65,
    ],
)
def test_baseline_cannot_bypass_canonical_program_series_key_grammar(series_key):
    with pytest.raises(ValueError, match="programSeriesKey must be 1-64 ASCII"):
        _policy().build_program_baseline_migration_policy(_evidence(series_key))
