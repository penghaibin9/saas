"""普通任课教师教务入口/教材/调停课安全回归锁。"""
from pathlib import Path
import inspect

from app.core.permissions import ROLE_PERMISSIONS
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook
from app.modules.academic_affairs.services import academic_affairs_schedule_change_r3_service as schedule_change

ROOT = Path(__file__).resolve().parents[1]


def _read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_academic_teacher_dashboard_permission_is_legacy_compatible_but_service_is_safe():
    granted = ROLE_PERMISSIONS["ACADEMIC_TEACHER"]
    assert "academicAffairs.dashboard.view" in granted
    service = _read("app/modules/academic_affairs/services/academic_affairs_service.py")
    teacher_branch = service[service.index('if role == "ACADEMIC_TEACHER"'):service.index('stu_total =', service.index('if role == "ACADEMIC_TEACHER"'))]
    assert '"summaryCards": []' in teacher_branch
    assert '"teacherSafeView": True' in teacher_branch
    assert "StudentProfile" not in teacher_branch
    assert "AaRegistration" not in teacher_branch


def test_attendance_frontend_permission_matches_backend_contract():
    routes = _read("../frontend/src/modules/academicAffairs/academic-affairs.routes.js")
    nav = _read("../frontend/src/config/navPlan.js")
    assert "meta('academicAffairs.attendance.view', '课堂考勤统计')" in routes
    attendance_block = nav[nav.index("mod('aa-attendance'"):nav.index("mod('aa-course-selection'")]
    assert "academicAffairs.warning.view" not in attendance_block
    assert attendance_block.count("academicAffairs.attendance.view") >= 3
    warning_block = nav[nav.index("mod('aa-warning'"):nav.index("mod('aa-graduation-qual'")]
    assert "academicAffairs.warning.view" in warning_block
    assert "academicAffairs.attendance.view" not in warning_block


def test_textbook_public_owner_enforces_teacher_object_scope_on_selection_commands():
    assert textbook.__name__.endswith("academic_affairs_textbook_final_facade")
    source = inspect.getsource(textbook)
    assert "_require_teacher_selection_scope" in source
    for name in ("create_selection", "submit_selection", "withdraw_selection"):
        fn_source = inspect.getsource(getattr(textbook, name))
        assert "_require_teacher_selection_scope" in fn_source


def test_textbook_sensitive_reads_no_longer_share_generic_teacher_view_permission():
    router = _read("app/modules/academic_affairs/routers/textbook_core_router.py")
    sensitive = [
        'review_batches', 'order_batches', 'order_batch_items', 'dist_records',
        'fee_ledger', 'textbook_stock', 'textbook_stats'
    ]
    for name in sensitive:
        start = router.index(f"def {name}")
        block = router[max(0, router.rfind("@router", 0, start)):router.find("\n\n", start)]
        assert "require_permission(_TB_VIEW)" not in block, name


def test_schedule_change_submit_uses_live_teacher_authority_not_schedule_snapshot():
    final_source = inspect.getsource(schedule_change.submit)
    assert "_teacher_key_for_origin" in final_source
    legacy = _read("app/modules/academic_affairs/services/academic_affairs_schedule_change_service.py")
    assert "teacher_authority.require_teacher" in legacy

def test_textbook_teacher_list_scope_follows_formal_handoff_or_original_applicant():
    source = _read("app/modules/academic_affairs/services/academic_affairs_textbook_service.py")
    start = source.index("def list_selections")
    end = source.index("\ndef _is_school", start)
    block = source[start:end]
    assert "teacher_authority.relation_scope" in block
    assert 'AaTextbookSelection.task_id.in_(sorted(formal_task_ids)' in block
    assert "AaTextbookSelection.officer_key.in_" in block
    assert "or_(" in block
