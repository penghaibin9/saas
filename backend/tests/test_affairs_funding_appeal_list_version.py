"""SA-004 funding appeal list must carry the optimistic-lock version used by Staff PC review."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.affairs_funding_service import _appeal_row


def test_funding_appeal_row_exposes_version_for_review_lock():
    appeal = SimpleNamespace(
        id=11,
        application_id=22,
        student_id=33,
        appellant_name="申诉人",
        reason="对公示结果申请复核",
        status="SUBMITTED",
        result=None,
        review_opinion=None,
        reviewer=None,
        reviewed_at=None,
        version=7,
    )

    row = _appeal_row(appeal)

    assert row["appealId"] == "11"
    assert row["status"] == "SUBMITTED"
    assert row["version"] == 7
