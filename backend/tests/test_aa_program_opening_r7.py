"""R7 培养方案校验器与开课差异行为回归。"""
from pathlib import Path
from types import SimpleNamespace


def test_opening_status_detects_hours_and_teacher_gaps():
    from app.modules.academic_affairs.services.academic_affairs_program_governance_service import _task_row_status

    program_course = SimpleNamespace(course_id=1, credit_snapshot=3)
    catalog = SimpleNamespace(credit=3, hours_total=48)

    status, _ = _task_row_status(program_course, catalog, [SimpleNamespace(total_hours=32, teacher_key="T001")])
    assert status == "HOURS_MISMATCH"
    status, _ = _task_row_status(program_course, catalog, [SimpleNamespace(total_hours=48, teacher_key="")])
    assert status == "NO_TEACHER"
    status, message = _task_row_status(program_course, catalog, [SimpleNamespace(total_hours=48, teacher_key="T001")])
    assert status == "READY"
    assert "学时一致" in message


def test_opening_summary_separates_blockers_from_missing_teacher():
    from app.modules.academic_affairs.services.academic_affairs_program_governance_service import _summary

    result = _summary([
        {"status": "READY"}, {"status": "NO_TEACHER"},
        {"status": "HOURS_MISMATCH"}, {"status": "OVER_OPENED"},
    ])
    assert result["total"] == 4
    assert result["ready"] == 1
    assert result["noTeacher"] == 1
    assert result["hoursMismatch"] == 1
    assert result["overOpened"] == 1
    assert result["blockerCount"] == 2
    assert result["canGenerateOrConfirm"] is False


def test_governance_source_includes_active_states_and_no_term_guessing():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/modules/academic_affairs/services/academic_affairs_program_governance_service.py").read_text(encoding="utf-8")

    assert '{"PUBLISHED", "ENABLED", "FROZEN"}' in source
    assert "系统未猜测全部课程" in source
    assert "AaProgram.status.in_" in source
    assert "HOURS_MISMATCH" in source
    assert "allowed_class_ids" in source


def test_program_submit_gate_rechecks_scope_and_locks_row():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/modules/academic_affairs/services/academic_affairs_program_service.py").read_text(encoding="utf-8")

    assert "governance._ensure_program_scope(db, user, int(program_id))" in source
    assert ".with_for_update().first()" in source
    assert '"PROGRAM_VALIDATION_BLOCKED"' in source
    assert '"issues": blockers[:20]' in source
    assert "sys.modules" not in source


def test_public_program_quality_router_uses_governance_service():
    from app.modules.academic_affairs.routers import program_quality_router

    assert program_quality_router.quality_svc.__name__.endswith(
        "academic_affairs_program_governance_service"
    )
    assert program_quality_router.quality_svc.opening_differences.__module__.endswith(
        "academic_affairs_program_governance_service"
    )


def test_opening_diff_ui_exposes_hours_gap_and_exact_fix_route():
    root = Path(__file__).resolve().parents[2]
    page = (root / "frontend/src/modules/academicAffairs/views/AaOpeningPlanDiffView.vue").read_text(encoding="utf-8")

    assert "HOURS_MISMATCH" in page
    assert "summary.hoursMismatch" in page
    assert "summary.canGenerateOrConfirm" in page
    assert "row.fixRoute" in page
    assert "责任对象" in page
