"""Stage D selection rule inventory must have business-owned remediation text."""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.academic_affairs.services.academic_affairs_decision_trace import SELECTION_RULE_CODES
from app.modules.academic_affairs.services.academic_affairs_selection_decision_trace import (
    _RESOLUTIONS,
    classify_selection_exception,
)


def test_every_frozen_selection_rule_has_business_owned_resolution():
    assert set(_RESOLUTIONS) == set(SELECTION_RULE_CODES)
    for rule_code, items in _RESOLUTIONS.items():
        assert items, rule_code
        assert all(str(item.get("code") or "").strip() for item in items)
        assert all(str(item.get("label") or "").strip() for item in items)


def test_already_passed_and_archived_paths_keep_deterministic_next_action():
    passed = AppException("DATA_CONFLICT", "该课程已修读通过，不可重复选课", http_status=409)
    archived = AppException("TERM_ARCHIVED", "学期已归档，禁止普通选课写入", http_status=409)

    assert classify_selection_exception(passed) == "COURSE_ALREADY_PASSED"
    assert _RESOLUTIONS["COURSE_ALREADY_PASSED"][0]["code"] == "VIEW_PASSED_GRADE"

    assert classify_selection_exception(archived) == "TERM_ARCHIVED"
    assert _RESOLUTIONS["TERM_ARCHIVED"][0]["code"] == "CONTACT_POST_ARCHIVE_CORRECTION"
