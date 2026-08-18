from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_c_attendance_has_one_command_transaction_owner():
    public = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py"
    )
    legacy = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_service.py"
    )
    command = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_guard.py"
    )
    read_guard = _read(
        "app/modules/academic_affairs/services/academic_affairs_attendance_teacher_relation_read_guard.py"
    )
    mobile_router = _read(
        "app/modules/academic_affairs/routers/mobile_grade_entry_router.py"
    )

    assert "AaAttendanceSession(" not in public
    assert "resolve_teaching_task_roster" not in public
    assert "return relation_guard.create_session(user, body)" in public
    assert "return relation_guard.get_session(session_id, user)" in public
    assert "return relation_guard.mark_attendance(session_id, user, body)" in public
    assert "return relation_guard.submit_session(session_id, user)" in public
    assert "return read_guard.list_sessions(" in public
    assert "return read_guard.attendance_stats(" in public
    assert "def resolve_versioned_roster(" in public
    assert "def freeze_consumer_snapshot(" in public
    assert "_STATUS_OK =" in public

    assert "AaAttendanceSession(" not in legacy
    assert "resolve_teaching_task_roster" not in legacy
    assert "academic_affairs_attendance_public_service as _public" in legacy
    assert "create_session = _public.create_session" in legacy
    assert "attendance_stats = _public.attendance_stats" in legacy

    assert "attendance_relation_guard.install()" not in mobile_router
    assert "attendance_relation_read_guard.install()" not in mobile_router
    assert (
        "mobile_public.teacher_attendance_class_options = "
        "attendance_relation_guard.teacher_attendance_class_options"
    ) in mobile_router

    assert "AaAttendanceSession(" in command
    assert "public._canonical" not in command
    assert "setattr(public" not in command
    for phantom in (
        "teaching_task_id=",
        "occurrence_identity=",
        "source_type=",
        "source_reason=",
        "source_evidence=",
    ):
        assert phantom not in command
    for needle in (
        "public.resolve_versioned_roster",
        "public.freeze_consumer_snapshot",
        "teacher_authority.require_teacher",
        "_guard_no_duplicate_occurrence",
        'f";occurrence={occurrence[\'occurrenceIdentity\']}"',
        'f";scheduleItem={occurrence[\'scheduleItemId\']}"',
        'f";activeBatch={occurrence[\'activeBatchId\']}"',
        'f";scope={occurrence[\'scopeType\']}:{occurrence[\'scopeId\']}"',
        'f";reason={special_reason};evidence={special_evidence}"',
        'result["occurrenceEvidence"]',
    ):
        assert needle in command

    assert "yield_per=500" in read_guard
    assert "select(func.count())" in read_guard
    assert "TEACHING_CLASS_TEACHER_BY_OCCURRENCE_WEEK" in read_guard


def test_c_w5_executable_evidence_assets_cover_the_full_teacher_chain():
    live = _read("scripts/e2e_academic_affairs_live_flow.py")
    round3 = _read("scripts/e2e_academic_affairs_round3.py")

    order = (
        "chain3_schedule_attendance()",
        "chain4_selection_exam()",
        "chain5_grades_warning()",
    )
    positions = [live.index(marker) for marker in order]
    assert positions == sorted(positions)

    for marker in (
        'C3.schedule_publish',
        'C3.schedule_four_end_read',
        'C3.schedule_change_apply',
        'C4.exam_invigilator',
        'C5.grade_draft',
        'C5.grade_submit',
        'C5.grade_college_return',
        'C5.grade_publish',
        'C5.transcript_four_end',
        'C0.multi_login',
        'C0.logout_invalidates_token',
    ):
        assert marker in live

    assert 'R3.att_submit' in round3
    assert '/attendance/sessions/{sid}/mark' in round3
    assert '/attendance/sessions/{sid}/submit' in round3
    assert 'no ScopeHead-active formal attendance occurrence accepted' in round3

    return_pos = live.index('C5.grade_college_return')
    publish_pos = live.index('C5.grade_publish')
    between = live[return_pos:publish_pos]
    assert between.count('/grade-tasks/{gtid}/submit') >= 1
    assert 'college-review' in between and '"APPROVE"' in between
