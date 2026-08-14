"""PR #101 production audit: student-level stats drilldowns mask student numbers."""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_stats_privacy_guard as guard
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy


def test_stats_privacy_guard_is_installed_on_current_legacy_student_drilldowns():
    assert legacy.registration_unregistered is guard.registration_unregistered
    assert legacy.warning_detail is guard.warning_detail
    assert legacy.status_change_detail is guard.status_change_detail
    assert legacy.grade_detail is guard.grade_detail
    for fn in (
        legacy.registration_unregistered,
        legacy.warning_detail,
        legacy.status_change_detail,
        legacy.grade_detail,
    ):
        assert getattr(fn, "_stats_student_privacy_guard", False) is True


def test_stats_privacy_mask_is_irreversible_for_display_contract():
    assert guard._mask_student_no("2026123456") == "20******56"
    assert guard._mask_student_no("1234") == "****"
    assert guard._mask_student_no("") == ""
    rows, total = guard._mask_rows(([
        {"studentNo": "2026123456", "studentName": "张三"},
        {"studentName": "李四"},
    ], 2))
    assert total == 2
    assert rows[0]["studentNo"] == "20******56"
    assert "2026123456" not in rows[0]["studentNo"]
    assert rows[0]["studentName"] == "张三"
    assert "studentNo" not in rows[1]


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 20), (-1, 20), ("bad", 20), (1, 0), (1, 201), (1, "bad")],
)
def test_stats_privacy_guard_rejects_invalid_paging_before_query(page, page_size):
    with pytest.raises(AppException) as exc:
        guard._page_values(page, page_size)
    assert exc.value.code == "VALIDATION_ERROR"
