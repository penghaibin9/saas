"""PR #101 production audit: student-level stats drilldowns keep frozen display policy and bounded paging."""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_stats_privacy_guard as guard
from app.modules.academic_affairs.services import academic_affairs_stats_service as public


def test_stats_paging_guard_is_installed_on_student_drilldowns():
    assert public.registration_unregistered is guard.registration_unregistered
    assert public.warning_detail is guard.warning_detail
    assert public.status_change_detail is guard.status_change_detail
    assert public.grade_detail is guard.grade_detail
    for fn in (
        public.registration_unregistered,
        public.warning_detail,
        public.status_change_detail,
        public.grade_detail,
    ):
        assert getattr(fn, "_stats_student_privacy_guard", False) is True


def test_authorized_student_number_display_contract_is_preserved(monkeypatch):
    expected = ([{"studentNo": "2026123456", "studentName": "张三"}], 1)
    monkeypatch.setattr(
        guard,
        "_ORIGINAL_GRADE",
        lambda _user, _term_id, _college_id, _course_name, _page, _page_size: expected,
    )
    rows, total = guard.grade_detail({}, page=1, page_size=20)
    assert total == 1
    assert rows[0]["studentNo"] == "2026123456"
    assert rows[0]["studentName"] == "张三"


def test_registration_student_number_display_contract_is_preserved(monkeypatch):
    expected = ([{"studentNo": "2024002", "studentName": "李四"}], 1)
    monkeypatch.setattr(
        guard,
        "_ORIGINAL_REGISTRATION",
        lambda _user, _term_id, _college_id, _major_id, _page, _page_size: expected,
    )
    rows, total = guard.registration_unregistered({}, page=1, page_size=20)
    assert total == 1
    assert rows[0]["studentNo"] == "2024002"


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 20), (-1, 20), ("bad", 20), (1, 0), (1, 201), (1, "bad")],
)
def test_stats_paging_guard_rejects_invalid_paging_before_query(page, page_size):
    with pytest.raises(AppException) as exc:
        guard._page_values(page, page_size)
    assert exc.value.code == "VALIDATION_ERROR"
