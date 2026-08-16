from __future__ import annotations

import inspect
from pathlib import Path

from app.modules.academic_affairs.services import academic_affairs_selection_core_service as core
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as final
from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile


def _block(source: str, start: str, end: str) -> str:
    left = source.index(start)
    right = source.index(end, left)
    return source[left:right]


def test_conflict_audit_helper_never_commits_and_commands_own_single_commit():
    core_source = Path(core.__file__).read_text(encoding="utf-8")
    helper = _block(core_source, "def _record_conflict_reject", "\ndef _validate_enroll")
    assert "db.commit(" not in helper
    legacy = inspect.getsource(core.student_enroll)
    assert legacy.count("_record_conflict_reject") == 1
    reject_at = legacy.index("_record_conflict_reject")
    assert "db.commit()" in legacy[reject_at:reject_at + 220]

    wrapper_source = inspect.getsource(final.student_enroll)
    assert "_selection_course_admission" in wrapper_source
    assert "_student_enroll_guarded" in wrapper_source
    guarded_source = inspect.getsource(final._student_enroll_guarded)
    assert guarded_source.count("_record_conflict_reject") == 1
    reject_at = guarded_source.index("_record_conflict_reject")
    assert "db.commit()" in guarded_source[reject_at:reject_at + 240]


def test_mobile_preflight_delegates_canonical_final_service_without_rule_copy():
    source = inspect.getsource(mobile.selection_preflight_my)
    assert "sel.student_preflight" in source
    for forbidden in ["_validate_enroll", "AcademicGrade", "AaScheduleItem", "db.commit"]:
        assert forbidden not in source


def test_portal_and_mobile_routes_expose_preflight_before_enroll():
    root = Path(__file__).resolve().parents[2]
    mobile_router = (root / "backend/app/api/v1/mobile.py").read_text(encoding="utf-8")
    portal_router = (root / "backend/app/student_portal/router.py").read_text(encoding="utf-8")
    assert mobile_router.index('/academic/selection/preflight') < mobile_router.index('/academic/selection/enroll')
    assert portal_router.index('/academic/course-selection/preflight') < portal_router.index('/academic/course-selection/enroll')
